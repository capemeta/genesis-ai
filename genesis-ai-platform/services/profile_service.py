"""
个人资料服务
将个人资料、头像和会话管理的核心逻辑收口到 service 层，避免 API 层承载业务细节。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BadRequestException, NotFoundException
from core.security.token_store import SessionService
from models.organization import Organization
from models.tenant import Tenant
from models.user import User
from schemas.profile import UserProfileResponse, UserProfileUpdate


class ProfileService:
    """个人资料服务"""

    ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/gif"}
    MAX_AVATAR_SIZE = 5 * 1024 * 1024
    DEFAULT_SETTINGS: Dict[str, str] = {
        "language": "zh",
        "timezone": "Asia/Shanghai",
        "theme": "system",
        "date_format": "YYYY-MM-DD",
        "time_format": "24h",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_my_profile(self, current_user: User) -> UserProfileResponse:
        """获取当前用户个人资料"""
        db_user = await self._get_db_user(current_user)
        return await self._build_profile_response(db_user)

    async def update_my_profile(
        self,
        current_user: User,
        profile_update: UserProfileUpdate,
        session_service: SessionService,
    ) -> UserProfileResponse:
        """更新当前用户个人资料"""
        db_user = await self._get_db_user(current_user)

        normalized_email = self._normalize_optional_text(profile_update.email)
        normalized_phone = self._normalize_optional_text(profile_update.phone)
        normalized_nickname = self._normalize_optional_text(profile_update.nickname)
        normalized_job_title = self._normalize_optional_text(profile_update.job_title)
        normalized_bio = self._normalize_optional_text(profile_update.bio)

        if normalized_email and await self._email_exists_globally(
            email=normalized_email,
            exclude_user_id=db_user.id,
        ):
            raise BadRequestException("该邮箱已被其他用户使用")

        if normalized_phone and await self._phone_exists_globally(
            phone=normalized_phone,
            exclude_user_id=db_user.id,
        ):
            raise BadRequestException("该手机号已被其他用户使用")

        if profile_update.nickname is not None:
            db_user.nickname = normalized_nickname
        if profile_update.email is not None and normalized_email != db_user.email:
            db_user.email = normalized_email
            db_user.email_verified_at = None
        if profile_update.phone is not None and normalized_phone != db_user.phone:
            db_user.phone = normalized_phone
            db_user.phone_verified_at = None
        if profile_update.job_title is not None:
            db_user.job_title = normalized_job_title
        if profile_update.bio is not None:
            db_user.bio = normalized_bio

        db_user.settings = self._merge_settings(
            current_settings=db_user.settings,
            updates={
                "language": profile_update.language,
                "timezone": profile_update.timezone,
                "theme": profile_update.theme,
                "date_format": profile_update.date_format,
                "time_format": profile_update.time_format,
            },
        )

        self._apply_update_audit(db_user, current_user)

        await self.db.commit()
        await self.db.refresh(db_user)
        await self._refresh_session_user_info(db_user, session_service)

        return await self._build_profile_response(db_user)

    async def upload_avatar(
        self,
        current_user: User,
        file: UploadFile,
        session_service: SessionService,
    ) -> Dict[str, str]:
        """上传并更新头像"""
        self._validate_avatar_type(file.content_type)
        file_content = await file.read()
        self._validate_avatar_size(len(file_content))

        upload_dir = Path("uploads/avatars")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_ext = self._resolve_avatar_extension(file.filename)
        filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = upload_dir / filename
        file_path.write_bytes(file_content)

        db_user = await self._get_db_user(current_user)
        db_user.avatar_url = f"/uploads/avatars/{filename}"
        self._apply_update_audit(db_user, current_user)

        await self.db.commit()
        await self.db.refresh(db_user)
        await self._refresh_session_user_info(db_user, session_service)

        return {"avatar_url": db_user.avatar_url or ""}

    @staticmethod
    async def get_my_sessions(
        current_user: User,
        session_service: SessionService,
        current_session_id: Optional[str],
    ) -> Dict[str, Any]:
        """获取当前用户会话列表"""
        sessions = await session_service.get_user_active_sessions(
            user_id=current_user.id,
            current_session_id=current_session_id,
        )
        return {"sessions": sessions, "total": len(sessions)}

    @staticmethod
    async def revoke_other_sessions(
        current_user: User,
        session_service: SessionService,
        current_session_id: Optional[str],
    ) -> Dict[str, int]:
        """注销除当前会话外的其他会话"""
        if not current_session_id:
            raise BadRequestException("无法获取当前会话信息")

        revoked_count = await session_service.revoke_other_sessions(
            user_id=current_user.id,
            current_session_id=current_session_id,
        )
        return {"revoked_count": revoked_count}

    @staticmethod
    async def revoke_session(
        current_user: User,
        session_service: SessionService,
        target_session_id: str,
        current_session_id: Optional[str],
    ) -> None:
        """注销指定会话"""
        if target_session_id == current_session_id:
            raise BadRequestException("不能注销当前会话，请使用登出功能")

        sessions = await session_service.get_user_active_sessions(
            user_id=current_user.id,
            current_session_id=current_session_id,
        )
        session_ids = {session["session_id"] for session in sessions}
        if target_session_id not in session_ids:
            raise NotFoundException("会话不存在或已过期")

        success = await session_service.revoke_session(target_session_id)
        if not success:
            raise BadRequestException("注销会话失败")

    async def _get_db_user(self, current_user: User) -> User:
        """查询数据库中的最新用户信息"""
        stmt = select(User).where(
            User.id == current_user.id,
            User.tenant_id == current_user.tenant_id,
            User.del_flag == "0",
        )
        result = await self.db.execute(stmt)
        db_user = result.scalar_one_or_none()
        if not db_user:
            raise NotFoundException("用户不存在")
        return db_user

    async def _build_profile_response(self, db_user: User) -> UserProfileResponse:
        """构建个人资料响应"""
        settings = self._resolve_settings(db_user.settings)
        tenant_name = await self._get_tenant_name(db_user.tenant_id)
        organization_name = await self._get_organization_name(db_user.organization_id)

        return UserProfileResponse(
            id=str(db_user.id),
            username=db_user.username,
            nickname=db_user.nickname,
            email=db_user.email,
            phone=db_user.phone,
            avatar_url=db_user.avatar_url,
            job_title=db_user.job_title,
            bio=db_user.bio,
            status=db_user.status,
            tenant_id=str(db_user.tenant_id),
            tenant_name=tenant_name,
            organization_id=str(db_user.organization_id) if db_user.organization_id else None,
            organization_name=organization_name,
            email_verified=db_user.email_verified,
            phone_verified=db_user.phone_verified,
            last_login_at=self._to_iso(db_user.last_login_at),
            last_login_ip=db_user.last_login_ip,
            last_active_at=self._to_iso(db_user.last_active_at),
            password_changed_at=self._to_iso(db_user.password_changed_at),
            language=settings["language"],
            timezone=settings["timezone"],
            theme=settings["theme"],
            date_format=settings["date_format"],
            time_format=settings["time_format"],
            created_at=self._to_iso(db_user.created_at) or "",
            updated_at=self._to_iso(db_user.updated_at) or "",
        )

    async def _get_tenant_name(self, tenant_id: Any) -> Optional[str]:
        """获取租户名称"""
        tenant = await self.db.get(Tenant, tenant_id)
        return tenant.name if tenant else None

    async def _get_organization_name(self, organization_id: Any) -> Optional[str]:
        """获取组织名称"""
        if not organization_id:
            return None
        organization = await self.db.get(Organization, organization_id)
        return organization.name if organization else None

    async def _email_exists_globally(self, email: str, exclude_user_id: Any) -> bool:
        """检查全局邮箱是否重复"""
        stmt = select(User.id).where(
            User.id != exclude_user_id,
            User.del_flag == "0",
            User.deleted_at.is_(None),
            func.lower(User.email) == email.lower(),
        )
        return await self.db.scalar(stmt) is not None

    async def _phone_exists_globally(self, phone: str, exclude_user_id: Any) -> bool:
        """检查全局手机号是否重复"""
        stmt = select(User.id).where(
            User.id != exclude_user_id,
            User.del_flag == "0",
            User.deleted_at.is_(None),
            User.phone == phone,
        )
        return await self.db.scalar(stmt) is not None

    async def _refresh_session_user_info(
        self,
        db_user: User,
        session_service: SessionService,
    ) -> None:
        """刷新所有活跃会话中的用户信息缓存"""
        await session_service.update_user_info_in_all_sessions(
            db_user.id,
            self._build_session_user_info(db_user),
        )

    def _build_session_user_info(self, db_user: User) -> Dict[str, Any]:
        """构建写入 session 缓存的轻量用户信息"""
        return {
            "id": str(db_user.id),
            "username": db_user.username,
            "email": db_user.email,
            "nickname": db_user.nickname,
            "is_active": db_user.is_active,
            "is_superuser": db_user.is_superuser,
            "avatar_url": db_user.avatar_url,
        }

    def _apply_update_audit(self, db_user: User, current_user: User) -> None:
        """更新审计字段"""
        now = datetime.now(timezone.utc)
        db_user.updated_by_id = current_user.id
        db_user.updated_by_name = current_user.nickname or current_user.username
        db_user.updated_at = now
        db_user.last_active_at = now

    def _resolve_settings(self, settings: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """合并个人偏好默认值"""
        merged = dict(self.DEFAULT_SETTINGS)
        if settings:
            for key in self.DEFAULT_SETTINGS:
                value = settings.get(key)
                if isinstance(value, str) and value.strip():
                    merged[key] = value.strip()
        return merged

    def _merge_settings(
        self,
        current_settings: Optional[Dict[str, Any]],
        updates: Dict[str, Optional[str]],
    ) -> Dict[str, Any]:
        """在保留现有扩展 key 的前提下更新统一偏好字段"""
        merged: Dict[str, Any] = dict(current_settings or {})
        for key, default_value in self.DEFAULT_SETTINGS.items():
            if key not in merged:
                merged[key] = default_value

        for key, value in updates.items():
            if value is not None:
                merged[key] = value

        return merged

    def _validate_avatar_type(self, content_type: Optional[str]) -> None:
        """校验头像文件类型"""
        if content_type not in self.ALLOWED_AVATAR_TYPES:
            allowed_types = ", ".join(sorted(self.ALLOWED_AVATAR_TYPES))
            raise BadRequestException(f"不支持的文件类型。支持的类型：{allowed_types}")

    def _validate_avatar_size(self, size: int) -> None:
        """校验头像文件大小"""
        if size > self.MAX_AVATAR_SIZE:
            raise BadRequestException("文件大小不能超过 5MB")

    def _resolve_avatar_extension(self, filename: Optional[str]) -> str:
        """解析头像文件后缀"""
        if filename and "." in filename:
            return filename.rsplit(".", 1)[-1].lower()
        return "jpg"

    def _normalize_optional_text(self, value: Optional[str]) -> Optional[str]:
        """对可选字符串进行裁剪和空值归一化"""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    def _to_iso(self, value: Optional[datetime]) -> Optional[str]:
        """统一时间序列化格式"""
        return value.isoformat() if value else None
