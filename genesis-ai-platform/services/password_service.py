"""
密码服务
收口修改密码等核心安全逻辑，避免 API 层承载业务细节。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import InvalidCredentialsException
from core.security import get_password_hash, verify_password
from core.security.token_store import SessionService
from models.user import User
from repositories.user_repo import UserRepository
from schemas.auth import PasswordChange


class PasswordService:
    """密码服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def change_password(
        self,
        password_change: PasswordChange,
        request: Request,
        current_user: User,
        session_service: SessionService,
    ) -> dict:
        """
        修改当前用户密码并按需撤销会话。
        """
        db_user = await self.user_repo.get(current_user.id)
        if not db_user:
            raise InvalidCredentialsException("用户不存在")

        if not verify_password(password_change.old_password, db_user.password_hash):
            raise InvalidCredentialsException("当前密码不正确")

        if password_change.old_password == password_change.new_password:
            raise InvalidCredentialsException("新密码不能与当前密码相同")

        now = datetime.now(timezone.utc)
        db_user.password_hash = get_password_hash(password_change.new_password)
        db_user.password_changed_at = now
        db_user.updated_by_id = current_user.id
        db_user.updated_by_name = current_user.display_name
        db_user.updated_at = now

        await self.db.commit()
        await self.db.refresh(db_user)

        current_session_id = self._get_current_session_id(request)
        revoked_count = 0

        try:
            if password_change.logout_all_devices:
                revoked_count = await session_service.revoke_all_user_sessions(current_user.id)
                return {
                    "message": "密码修改成功，已登出所有设备（包括当前设备），请重新登录",
                    "revoked_count": revoked_count,
                }

            if current_session_id:
                revoked_count = await session_service.revoke_other_sessions(
                    user_id=current_user.id,
                    current_session_id=current_session_id,
                )
            else:
                revoked_count = await session_service.revoke_all_user_sessions(current_user.id)

            if revoked_count > 0:
                return {
                    "message": f"密码修改成功，已登出其他 {revoked_count} 个设备",
                    "revoked_count": revoked_count,
                }

            return {"message": "密码修改成功", "revoked_count": 0}
        except Exception:
            return {
                "message": "密码修改成功（部分设备可能仍保持登录状态，建议手动登出所有设备）",
                "revoked_count": revoked_count,
            }

    def _get_current_session_id(self, request: Request) -> str | None:
        """兼容 Cookie 与 Bearer 两种认证方式获取当前会话 ID。"""
        cookie_session_id = request.cookies.get("access_token")
        if cookie_session_id:
            return cookie_session_id

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None
