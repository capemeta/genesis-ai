"""
密码相关 API
密码强度检查、密码修改、密码重置等
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_async_session
from core.security import get_current_active_user, PasswordValidator, get_session_service
from core.security.token_store import SessionService
from core.response import ResponseBuilder
from schemas.auth import PasswordChange
from models.user import User
from services.password_service import PasswordService

router = APIRouter()


class PasswordStrengthRequest(BaseModel):
    """密码强度检查请求"""
    password: str = Field(..., description="待检查的密码")


class PasswordStrengthResponse(BaseModel):
    """密码强度检查响应"""
    is_valid: bool = Field(..., description="是否符合要求")
    score: int = Field(..., description="强度分数 (0-100)")
    label: str = Field(..., description="强度标签")
    errors: list[str] = Field(default_factory=list, description="错误信息列表")
    requirements: dict = Field(..., description="密码要求说明")


class PasswordChangeResponse(BaseModel):
    """密码修改响应"""
    message: str = Field(..., description="响应消息")


@router.post("/check-strength")
async def check_password_strength(request: PasswordStrengthRequest):
    """
    检查密码强度
    
    不需要登录即可使用，用于注册时实时检查密码强度
    """
    is_valid, errors = PasswordValidator.validate(request.password)
    score = PasswordValidator.get_strength_score(request.password)
    label = PasswordValidator.get_strength_label(score)
    requirements = PasswordValidator.get_requirements()
    
    return ResponseBuilder.build_success(
        data={
            "is_valid": is_valid,
            "score": score,
            "label": label,
            "errors": errors,
            "requirements": requirements
        },
        message="密码强度检查完成"
    )


@router.get("/requirements")
async def get_password_requirements():
    """
    获取密码要求
    
    返回密码策略和要求说明
    """
    return ResponseBuilder.build_success(
        data=PasswordValidator.get_requirements(),
        message="获取密码要求成功"
    )


@router.post("/change")
async def change_password(
    password_change: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
    session_service: SessionService = Depends(get_session_service),
):
    """
    修改密码
    
    需要提供当前密码进行验证
    
    参数：
    - old_password: 当前密码
    - new_password: 新密码
    - logout_all_devices: 是否登出所有设备（包括当前设备）
      - False（默认）：保留当前设备登录，登出其他设备
      - True：登出所有设备（包括当前设备），需要重新登录
    
    安全措施：
    - 验证旧密码
    - 检查新旧密码是否相同
    - 根据用户选择撤销 session
    - 记录审计日志
    """
    service = PasswordService(db)
    result = await service.change_password(
        password_change=password_change,
        request=request,
        current_user=current_user,
        session_service=session_service,
    )
    return ResponseBuilder.build_success(
        data={"revoked_count": result["revoked_count"]},
        message=result["message"],
    )
