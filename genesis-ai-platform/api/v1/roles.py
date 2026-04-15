"""
角色管理 API
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_async_session
from core.security.auth import get_current_user
from core.security.permissions import has_perms
from core.response import ResponseBuilder
from models.user import User
from models.role import Role
from models.user_roles import user_roles
from models.role_permissions import role_permissions
from schemas.role import (
    RoleCreate,
    RoleUpdate,
    RoleRead,
    RoleListItem,
    RoleListResponse,
    RoleDeleteRequest,
    RoleAssignPermissionsRequest,
)
from schemas.permission import PermissionRead
from services.role_service import RoleService

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/list", dependencies=[has_perms("settings:roles:query")])
async def list_roles(
    search: str | None = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    获取角色列表
    
    支持搜索
    """
    service = RoleService(db)
    roles, total = await service.list_roles(
        tenant_id=current_user.tenant_id,
        search=search,
    )
    
    # 构建响应数据
    role_items = [RoleListItem.model_validate(role) for role in roles]
    
    return ResponseBuilder.build_success(
        data={"data": [item.model_dump() for item in role_items], "total": total},
        message="查询成功",
    )


@router.get("/assignable-roles", dependencies=[has_perms("settings:users:create", "settings:users:edit")])
async def get_assignable_roles(
    page: int | None = Query(None, ge=1, description="页码"),
    page_size: int | None = Query(None, ge=1, le=100, description="每页数量"),
    search: str | None = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    获取用户可分配的角色列表
    
    过滤条件：
    - 未删除的角色
    - 已启用的角色
    - 如果当前用户不是超级管理员，过滤掉超级管理员角色
    
    支持分页和搜索
    """
    service = RoleService(db)
    
    # 如果提供了分页参数，返回分页数据
    if page is not None and page_size is not None:
        roles, total = await service.get_assignable_roles_paginated(
            tenant_id=current_user.tenant_id,
            current_user=current_user,
            page=page,
            page_size=page_size,
            search=search,
        )
        
        # 构建响应数据
        role_items = [RoleListItem.model_validate(role) for role in roles]
        
        return ResponseBuilder.build_success(
            data={"data": [item.model_dump() for item in role_items], "total": total},
            message="查询成功",
        )
    else:
        # 兼容旧接口：不分页，返回所有数据
        roles = await service.get_assignable_roles(
            tenant_id=current_user.tenant_id,
            current_user=current_user,
        )
        
        # 构建响应数据
        role_items = [RoleListItem.model_validate(role) for role in roles]
        
        return ResponseBuilder.build_success(
            data=[item.model_dump() for item in role_items],
            message="查询成功",
        )



@router.get("/get", dependencies=[has_perms("settings:roles:query")])
async def get_role(
    id: UUID = Query(..., description="角色ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """获取角色详情"""
    service = RoleService(db)
    role = await service.get_role(id, current_user.tenant_id)
    
    return ResponseBuilder.build_success(
        data=RoleRead.model_validate(role).model_dump(),
        message="查询成功",
    )


@router.post("/create", dependencies=[has_perms("settings:roles:create")])
async def create_role(
    data: RoleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """创建角色"""
    service = RoleService(db)
    role = await service.create_role(
        data=data,
        tenant_id=current_user.tenant_id,
        current_user=current_user,
    )
    
    return ResponseBuilder.build_success(
        data=RoleRead.model_validate(role).model_dump(),
        message="创建成功",
        http_status=status.HTTP_201_CREATED,
    )


@router.post("/update", dependencies=[has_perms("settings:roles:edit")])
async def update_role(
    data: RoleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """更新角色"""
    service = RoleService(db)
    role = await service.update_role(
        role_id=data.id,
        data=data,
        tenant_id=current_user.tenant_id,
        current_user=current_user,
    )
    
    return ResponseBuilder.build_success(
        data=RoleRead.model_validate(role).model_dump(),
        message="更新成功",
    )


@router.post("/delete", dependencies=[has_perms("settings:roles:delete")])
async def delete_role(
    data: RoleDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """删除角色（逻辑删除）"""
    service = RoleService(db)
    await service.delete_role(data.id, current_user.tenant_id, current_user)
    
    return ResponseBuilder.build_success(
        data={"id": str(data.id)},
        message="删除成功",
    )


@router.post("/assign-permissions", dependencies=[has_perms("settings:roles:edit")])
async def assign_role_permissions(
    data: RoleAssignPermissionsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """为角色分配权限"""
    service = RoleService(db)
    await service.assign_permissions(
        role_id=data.role_id,
        permission_ids=data.permission_ids,
        tenant_id=current_user.tenant_id,
    )
    
    return ResponseBuilder.build_success(
        data={"role_id": str(data.role_id), "permission_ids": [str(pid) for pid in data.permission_ids]},
        message="权限分配成功",
    )


@router.get("/get-permissions", dependencies=[has_perms("settings:roles:query")])
async def get_role_permissions(
    role_id: UUID = Query(..., description="角色ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """获取角色权限"""
    service = RoleService(db)
    permissions = await service.get_role_permissions(role_id, current_user.tenant_id)
    
    return ResponseBuilder.build_success(
        data=[PermissionRead.model_validate(perm).model_dump() for perm in permissions],
        message="查询成功",
    )


@router.get("/get-users", dependencies=[has_perms("settings:roles:query")])
async def get_role_users(
    role_id: UUID = Query(..., description="角色ID"),
    search: str | None = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """获取角色的用户列表"""
    service = RoleService(db)
    users, total = await service.get_role_users(role_id, current_user.tenant_id, search)
    
    # 构建响应数据
    user_items = [
        {
            "id": str(user.id),
            "username": user.username,
            "nickname": user.nickname,
            "email": user.email,
            "status": user.status,
        }
        for user in users
    ]
    
    return ResponseBuilder.build_success(
        data={"data": user_items, "total": total},
        message="查询成功",
    )


@router.get("/get-available-users", dependencies=[has_perms("settings:roles:query")])
async def get_available_users(
    role_id: UUID = Query(..., description="角色ID"),
    search: str | None = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """获取可分配的用户列表（未分配该角色的用户）"""
    service = RoleService(db)
    users, total = await service.get_available_users(role_id, current_user.tenant_id, search)
    
    # 构建响应数据
    user_items = [
        {
            "id": str(user.id),
            "username": user.username,
            "nickname": user.nickname,
            "email": user.email,
            "status": user.status,
        }
        for user in users
    ]
    
    return ResponseBuilder.build_success(
        data={"data": user_items, "total": total},
        message="查询成功",
    )


@router.post("/assign-users", dependencies=[has_perms("settings:roles:edit")])
async def assign_role_users(
    role_id: UUID = Body(...),
    user_ids: list[UUID] = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """为角色分配用户"""
    service = RoleService(db)
    await service.assign_users(
        role_id=role_id,
        user_ids=user_ids,
        tenant_id=current_user.tenant_id,
    )
    
    return ResponseBuilder.build_success(
        data={"role_id": str(role_id), "user_ids": [str(uid) for uid in user_ids]},
        message="用户分配成功",
    )


@router.post("/remove-user", dependencies=[has_perms("settings:roles:edit")])
async def remove_role_user(
    role_id: UUID = Body(...),
    user_id: UUID = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """取消用户的角色"""
    service = RoleService(db)
    await service.remove_user(
        role_id=role_id,
        user_id=user_id,
        tenant_id=current_user.tenant_id,
    )
    
    return ResponseBuilder.build_success(
        data={"role_id": str(role_id), "user_id": str(user_id)},
        message="用户移除成功",
    )
