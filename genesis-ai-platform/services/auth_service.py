"""
认证服务
统一处理登录身份解析、全局唯一账号语义和账户安全状态，避免认证逻辑散落在 API 层。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import json
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BadRequestException, TooManyRequestsException, UserAlreadyExistsException
from core.security.crypto import get_password_hash, verify_password
from core.security.token_store import SessionService
from models.user import User
from repositories.user_repo import UserRepository
from schemas.auth import RegisterRequest
from services.permission_service import PermissionService
from services.role_service import RoleService


class AuthService:
    """认证服务"""

    LOGIN_LOCK_THRESHOLD = 5
    LOGIN_LOCK_MINUTES = 15
    DUMMY_HASH = (
        "$argon2id$v=19$m=65536,t=3,p=4$H+O8957zXmuN8T6HsLbW2g$"
        "QB6GmxHVWv8Bs7jivyc4Z9mXtLhkPXxHAnFG/UIBmZo"
    )
    DEFAULT_SCOPE = ["read", "write"]

    logger = logging.getLogger(__name__)

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def authenticate_user(
        self,
        username_or_email: str,
        password: str,
    ) -> User | None:
        """按全局唯一登录标识认证用户"""
        normalized_identifier = username_or_email.strip()
        candidates = await self.user_repo.list_by_username_or_email(normalized_identifier)

        if not candidates:
            verify_password(password, self.DUMMY_HASH)
            return None

        user = candidates[0]
        await self._ensure_user_can_login(user)

        if not verify_password(password, user.password_hash):
            await self._record_failed_login(user)
            return None

        self._clear_failed_login_state(user)
        return user

    async def register_user(self, register_data: RegisterRequest) -> User:
        """按全局唯一登录标识注册用户"""
        if await self.user_repo.exists_by_username(register_data.username):
            raise UserAlreadyExistsException("用户名已存在")

        if register_data.email and await self.user_repo.exists_by_email(register_data.email):
            raise UserAlreadyExistsException("邮箱已被使用")

        user = User(
            tenant_id=register_data.tenant_id,
            username=register_data.username.strip(),
            email=register_data.email,
            password_hash=get_password_hash(register_data.password),
            nickname=register_data.nickname,
            activated_at=datetime.now(timezone.utc),
        )

        return await self.user_repo.create(user)

    async def create_session_payload(
        self,
        user: User,
        session_service: SessionService,
        client_ip: str,
        user_agent: str | None,
        remember: bool = False,
        requested_scope: list[str] | None = None,
    ) -> dict:
        """
        为用户创建登录会话数据。

        说明：
        - 角色、权限和 session 缓存信息统一在这里构建
        - API 层只负责 Cookie 设置和响应包装
        """
        from core.config import settings

        authorization_snapshot = await self.get_authorization_snapshot(user)
        granted_scope = self._build_granted_scope(
            user=user,
            requested_scope=requested_scope,
        )

        access_expire = None
        refresh_expire = None
        if remember:
            access_expire = timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER
            )
            refresh_expire = timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER
            )

        return await session_service.create_session_pair(
            user_id=user.id,
            tenant_id=user.tenant_id,
            client_ip=client_ip,
            user_agent=user_agent,
            scope=granted_scope,
            user_info=authorization_snapshot["user_info"],
            custom_access_expire=access_expire,
            custom_refresh_expire=refresh_expire,
        )

    async def refresh_session_payload(
        self,
        refresh_session_id: str,
        session_service: SessionService,
        client_ip: str,
        user_agent: str | None,
    ) -> tuple[dict, User, bool]:
        """
        刷新会话并返回最新 session 数据与用户对象。

        返回 user 主要用于 API 层记录日志或补充响应。
        """
        refresh_ttl = await session_service.session_store.redis.ttl(
            f"{session_service.session_store.REFRESH_SESSION_PREFIX}{refresh_session_id}"
        )
        is_remember = refresh_ttl > 7 * 24 * 3600

        refresh_session = await session_service.verify_session(refresh_session_id)
        user_id = UUID(refresh_session["user_id"])

        user = await self.user_repo.get(user_id)
        if not user or not user.is_active:
            raise BadRequestException("用户不存在或已被禁用")

        authorization_snapshot = await self.get_authorization_snapshot(user)
        session_data = await session_service.refresh_session(
            refresh_session_id=refresh_session_id,
            client_ip=client_ip,
            user_agent=user_agent,
            user_info=authorization_snapshot["user_info"],
        )
        return session_data, user, is_remember

    async def get_authorization_snapshot(self, user: User) -> dict:
        """
        统一加载角色、权限与 session 缓存用户信息。
        """
        role_service = RoleService(self.db)
        permission_service = PermissionService(self.db)

        role_codes = await role_service.get_user_role_codes(user.id, user.tenant_id)
        user.roles = role_codes
        permission_codes = await permission_service.get_user_permissions_with_user(
            user,
            use_cache=False,
        )

        return {
            "roles": role_codes,
            "permissions": permission_codes,
            "user_info": self._build_user_info(user, role_codes, permission_codes),
        }

    async def build_me_payload(
        self,
        user: User,
        session_service: SessionService,
    ) -> dict:
        """
        构建 `/auth/me` 返回结果并同步刷新 session 缓存。
        """
        authorization_snapshot = await self.get_authorization_snapshot(user)
        user.permissions = authorization_snapshot["permissions"]
        try:
            await session_service.refresh_user_info_in_sessions(user)
        except Exception as exc:
            self.logger.error("刷新 session 用户缓存失败: %s", exc, exc_info=True)

        return {
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "tenant_id": str(user.tenant_id),
            },
            "roles": authorization_snapshot["roles"],
            "permissions": authorization_snapshot["permissions"],
        }

    async def logout(
        self,
        request: Request,
        session_service: SessionService,
    ) -> None:
        """
        统一处理登出逻辑。

        设计目标：
        - API 层只负责清理 Cookie 和返回响应
        - service 层负责 session 解析、撤销和日志
        """
        client_ip = self._get_client_ip(request)
        session_id = self._get_request_session_id(request)

        if not session_id:
            self.logger.info("Logout request without session_id from %s", client_ip)
            return

        try:
            session_info = await self._resolve_logout_session_info(
                session_id=session_id,
                session_service=session_service,
            )
            await self._revoke_logout_sessions(
                session_id=session_id,
                session_info=session_info,
                session_service=session_service,
            )
            self.logger.info(
                "User logout handled: user_id=%s, ip=%s, session_id=%s",
                session_info["user_id"],
                client_ip,
                session_id,
            )
        except Exception as exc:
            self.logger.warning("Error during logout session processing: %s", exc)

    async def _ensure_user_can_login(self, user: User) -> None:
        """校验用户当前是否允许登录"""
        now = datetime.now(timezone.utc)

        if user.locked_until and user.locked_until > now:
            remaining_seconds = max(int((user.locked_until - now).total_seconds()), 1)
            raise TooManyRequestsException(
                f"账号已锁定，请在 {remaining_seconds} 秒后重试"
            )

        if user.locked_until and user.locked_until <= now:
            self._clear_failed_login_state(user)

        if user.status == "disabled":
            raise BadRequestException("账号已被禁用，请联系管理员")

    async def _record_failed_login(self, user: User) -> None:
        """记录登录失败并在达到阈值后锁定账号"""
        now = datetime.now(timezone.utc)
        user.failed_login_count = (user.failed_login_count or 0) + 1
        user.updated_at = now

        if user.failed_login_count >= self.LOGIN_LOCK_THRESHOLD:
            user.status = "locked"
            user.locked_until = now + timedelta(minutes=self.LOGIN_LOCK_MINUTES)

        await self.db.commit()
        await self.db.refresh(user)

    def _clear_failed_login_state(self, user: User) -> None:
        """清理登录失败状态"""
        user.failed_login_count = 0
        user.locked_until = None
        if user.status == "locked":
            user.status = "active"

    def _build_granted_scope(
        self,
        user: User,
        requested_scope: list[str] | None,
    ) -> list[str]:
        """
        统一计算最终授予的 scope。
        """
        user_scope = list(self.DEFAULT_SCOPE)
        if user.is_superuser:
            user_scope.append("admin")

        if not requested_scope:
            return user_scope

        requested_scope_set = set(requested_scope)
        return [scope for scope in user_scope if scope in requested_scope_set]

    def _build_user_info(
        self,
        user: User,
        role_codes: list[str],
        permission_codes: list[str],
    ) -> dict:
        """
        构建缓存到 session 的用户快照。
        """
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "nickname": user.nickname,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "avatar_url": user.avatar_url,
            "roles": role_codes,
            "permissions": permission_codes,
        }

    def _get_request_session_id(self, request: Request) -> str | None:
        """从请求中提取当前 access session ID。"""
        cookie_session_id = request.cookies.get("access_token")
        if cookie_session_id:
            return cookie_session_id

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None

    def _get_client_ip(self, request: Request) -> str:
        """延迟导入请求工具，避免 service 依赖过重。"""
        from utils.request_utils import get_client_ip

        return get_client_ip(request)

    async def _resolve_logout_session_info(
        self,
        session_id: str,
        session_service: SessionService,
    ) -> dict:
        """
        解析登出所需的 access/refresh 关联信息。
        """
        access_session = await session_service.session_store.read_session(session_id)
        if access_session:
            return {
                "user_id": access_session.get("user_id"),
                "refresh_session_id": access_session.get("refresh_session_id"),
            }

        session_json = await session_service.session_store.redis.get(
            f"{session_service.session_store.ACCESS_SESSION_PREFIX}{session_id}"
        )
        if not session_json:
            return {"user_id": None, "refresh_session_id": None}

        try:
            access_session = json.loads(session_json)
        except Exception as exc:
            self.logger.error("Failed to parse session JSON during logout: %s", exc)
            return {"user_id": None, "refresh_session_id": None}

        return {
            "user_id": access_session.get("user_id"),
            "refresh_session_id": access_session.get("refresh_session_id"),
        }

    async def _revoke_logout_sessions(
        self,
        session_id: str,
        session_info: dict,
        session_service: SessionService,
    ) -> None:
        """
        根据解析结果撤销 access/refresh session。
        """
        refresh_session_id = session_info.get("refresh_session_id")
        user_id = session_info.get("user_id")

        if not refresh_session_id and not user_id:
            self.logger.warning(
                "Cannot find session info for access_session %s, only clearing cookies",
                session_id,
            )
            return

        if not refresh_session_id and user_id:
            self.logger.warning(
                "Cannot find refresh_session_id for access_session %s, revoke all sessions for user %s",
                session_id,
                user_id,
            )
            try:
                revoked_count = await session_service.revoke_all_user_sessions(UUID(user_id))
                self.logger.info(
                    "Revoked all %s sessions for user %s during logout fallback",
                    revoked_count,
                    user_id,
                )
            except Exception as exc:
                self.logger.warning("Failed to revoke all sessions: %s", exc)
            return

        revoked_access = await session_service.revoke_session(session_id)
        if revoked_access:
            self.logger.info("Access session %s revoked", session_id)
        else:
            self.logger.warning("Access session %s was already revoked or expired", session_id)

        revoked_refresh = await session_service.revoke_session(str(refresh_session_id or ""))
        if revoked_refresh:
            self.logger.info("Refresh session %s revoked", refresh_session_id)
        else:
            self.logger.warning(
                "Refresh session %s was already revoked or expired",
                refresh_session_id,
            )
