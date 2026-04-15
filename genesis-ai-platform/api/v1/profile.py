"""
用户个人信息 API
"""
import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from core.response import ResponseBuilder
from core.security import get_session_service
from core.security.auth import get_current_user
from core.security.token_store import SessionService
from models.user import User
from schemas.profile import UserProfileUpdate
from services.profile_service import ProfileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


def _get_current_session_id(request: Request) -> str | None:
    """从请求中提取当前会话 ID"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.cookies.get("access_token")


@router.get("/me")
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    获取当前用户的个人信息
    """
    service = ProfileService(session)
    profile_data = await service.get_my_profile(current_user)
    return ResponseBuilder.build_success(
        data=profile_data.model_dump(),
        message="获取个人信息成功",
    )


@router.put("/me")
async def update_my_profile(
    profile_update: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    session_service: SessionService = Depends(get_session_service),
):
    """
    更新当前用户的个人信息
    """
    service = ProfileService(session)
    profile_data = await service.update_my_profile(
        current_user=current_user,
        profile_update=profile_update,
        session_service=session_service,
    )
    return ResponseBuilder.build_success(
        data=profile_data.model_dump(),
        message="更新个人信息成功",
    )


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    session_service: SessionService = Depends(get_session_service),
):
    """
    上传用户头像
    """
    service = ProfileService(session)
    data = await service.upload_avatar(
        current_user=current_user,
        file=file,
        session_service=session_service,
    )
    return ResponseBuilder.build_success(
        data=data,
        message="头像上传成功",
    )


@router.get("/sessions")
async def get_my_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    """
    获取当前用户的所有活跃会话
    """
    data = await ProfileService.get_my_sessions(
        current_user=current_user,
        session_service=session_service,
        current_session_id=_get_current_session_id(request),
    )
    return ResponseBuilder.build_success(
        data=data,
        message="获取会话列表成功",
    )


@router.delete("/sessions/others")
async def revoke_other_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    """
    注销所有其他设备的会话（保留当前会话）

    注意：此路由必须在 /sessions/{session_id} 之前定义，
    否则 'others' 会被当作 session_id 参数处理
    """
    data = await ProfileService.revoke_other_sessions(
        current_user=current_user,
        session_service=session_service,
        current_session_id=_get_current_session_id(request),
    )
    return ResponseBuilder.build_success(
        data=data,
        message=f"已注销 {data['revoked_count']} 个其他设备的会话",
    )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    """
    注销指定会话

    注意：不能注销当前会话
    """
    await ProfileService.revoke_session(
        current_user=current_user,
        session_service=session_service,
        target_session_id=session_id,
        current_session_id=_get_current_session_id(request),
    )
    return ResponseBuilder.build_success(
        message="会话已注销",
    )
