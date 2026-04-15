"""
用户管理 API
"""
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from core.security.auth import get_current_user
from core.security import get_session_service
from core.security.token_store import SessionService
from core.security.permissions import has_perms
from core.response import ResponseBuilder
from models.user import User
from schemas.user import (
    UserCreate,
    UserUpdate,
    UserRead,
    UserDeleteRequest,
    UserAssignRolesRequest,
    UserResetPasswordRequest,
)
from services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/list", dependencies=[has_perms("settings:users:query")])
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: str | None = Query(None, description="搜索关键词"),
    status: str | None = Query(None, description="状态过滤"),
    organization_id: UUID | None = Query(None, description="组织ID过滤"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    获取用户列表
    
    支持分页、搜索、状态过滤、组织过滤
    """
    service = UserService(db)
    user_items, total = await service.list_user_items(
        tenant_id=current_user.tenant_id,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        organization_id=organization_id,
    )

    return ResponseBuilder.build_success(
        data={"data": [item.model_dump() for item in user_items], "total": total},
        message="查询成功",
    )


@router.get("/get", dependencies=[has_perms("settings:users:query")])
async def get_user(
    id: UUID = Query(..., description="用户ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """获取用户详情"""
    service = UserService(db)
    user = await service.get_user_detail(id, current_user.tenant_id)
    
    return ResponseBuilder.build_success(
        data=user.model_dump(),
        message="查询成功",
    )



@router.post("/create", dependencies=[has_perms("settings:users:create")])
async def create_user(
    data: UserCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """创建用户"""
    service = UserService(db)
    user = await service.create_user(
        data=data,
        tenant_id=current_user.tenant_id,
        current_user=current_user,
    )
    
    return ResponseBuilder.build_success(
        data=UserRead.model_validate(user).model_dump(),
        message="创建成功",
        http_status=status.HTTP_201_CREATED,
    )


@router.post("/update", dependencies=[has_perms("settings:users:edit")])
async def update_user(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """更新用户"""
    service = UserService(db)
    user = await service.update_user(
        user_id=data.id,
        data=data,
        tenant_id=current_user.tenant_id,
        current_user=current_user,
    )
    
    return ResponseBuilder.build_success(
        data=UserRead.model_validate(user).model_dump(),
        message="更新成功",
    )


@router.post("/delete", dependencies=[has_perms("settings:users:delete")])
async def delete_user(
    data: UserDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """删除用户"""
    service = UserService(db)
    await service.delete_user(data.id, current_user.tenant_id)
    
    return ResponseBuilder.build_success(
        data={"id": str(data.id)},
        message="删除成功",
    )


@router.post("/assign-roles", dependencies=[has_perms("settings:users:edit")])
async def assign_user_roles(
    data: UserAssignRolesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """为用户分配角色"""
    service = UserService(db)
    await service.assign_roles(
        user_id=data.user_id,
        role_ids=data.role_ids,
        tenant_id=current_user.tenant_id,
    )
    
    return ResponseBuilder.build_success(
        data={"user_id": str(data.user_id), "role_ids": [str(rid) for rid in data.role_ids]},
        message="角色分配成功",
    )


@router.get("/get-roles", dependencies=[has_perms("settings:users:query")])
async def get_user_roles(
    user_id: UUID = Query(..., description="用户ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """获取用户角色"""
    service = UserService(db)
    roles = await service.get_user_roles(user_id, current_user.tenant_id)
    
    from schemas.role import RoleRead
    return ResponseBuilder.build_success(
        data=[RoleRead.model_validate(role).model_dump() for role in roles],
        message="查询成功",
    )


@router.post("/reset-password", dependencies=[has_perms("settings:users:edit")])
async def reset_user_password(
    data: UserResetPasswordRequest,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_async_session),
):
    """重置用户密码（管理员操作）"""
    service = UserService(db)
    
    user, revoked_count = await service.reset_password(
        user_id=data.user_id,
        new_password=data.new_password,
        tenant_id=current_user.tenant_id,
        session_service=session_service,
        current_user=current_user,
    )
    
    return ResponseBuilder.build_success(
        data={"user_id": str(user.id), "revoked_count": revoked_count},
        message="密码重置成功，已强制用户重新登录",
    )
