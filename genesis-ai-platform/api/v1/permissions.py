"""
权限管理 API
提供权限树、权限分配等额外功能
"""
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from core.database import get_async_session
from core.security.auth import get_current_active_user
from core.security.permissions import has_perms
from core.response import ResponseBuilder
from models.user import User
from services.permission_service import PermissionService
from schemas.permission import (
    PermissionCreate,
    PermissionUpdate,
    PermissionRead,
    PermissionListItem,
    PermissionListResponse,
    PermissionDeleteRequest
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/permissions", tags=["permissions"])


def get_permission_service(session: AsyncSession = Depends(get_async_session)) -> PermissionService:
    """获取权限服务实例"""
    return PermissionService(session)


# ==================== 查询接口 ====================

@router.get("/list", dependencies=[has_perms("settings:permissions:query")])
async def list_permissions(
    search: str | None = Query(None, description="搜索关键词（模糊匹配 code, name, module）"),
    type: str | None = Query(None, description="权限类型过滤（menu/function/directory）"),
    module: str | None = Query(None, description="模块过滤"),
    status: int | None = Query(None, description="状态过滤（0-正常，1-停用）"),
    current_user: User = Depends(get_current_active_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    获取权限列表
    
    权限：任何登录用户
    
    参数：
    - search: 搜索关键词（模糊匹配 code, name, module）
    - type: 权限类型过滤（menu/function/directory）
    - module: 模块过滤
    - status: 状态过滤（0-正常，1-停用）
    
    返回格式：
    {
        "code": 200,
        "message": "查询成功",
        "data": {
            "data": [...],
            "total": 10
        }
    }
    """
    permission_list, total = await permission_service.list_permissions(
        tenant_id=current_user.tenant_id,
        search=search,
        type_filter=type,
        module_filter=module,
        status_filter=status
    )
    
    return ResponseBuilder.build_success(
        data={
            "data": [PermissionListItem.model_validate(perm).model_dump() for perm in permission_list],
            "total": total
        },
        message="查询成功"
    )


@router.get("/get", dependencies=[has_perms("settings:permissions:query")])
async def get_permission(
    id: UUID = Query(..., description="权限ID"),
    current_user: User = Depends(get_current_active_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    获取权限详情
    
    权限：任何登录用户
    
    参数：
    - id: 权限ID（必填）
    
    返回格式：
    {
        "code": 200,
        "message": "查询成功",
        "data": {...}
    }
    """
    permission = await permission_service.get_permission(
        permission_id=id,
        tenant_id=current_user.tenant_id
    )
    
    return ResponseBuilder.build_success(
        data=PermissionRead.model_validate(permission).model_dump(),
        message="查询成功"
    )


@router.post("/tree", dependencies=[has_perms("settings:permissions:query")])
async def get_permission_tree(
    permission_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    获取权限树（用于权限分配界面）
    
    权限要求：permission:read 或 admin
    
    Args:
        permission_type: 权限类型过滤（menu/function），不传则返回所有
    
    Returns:
        权限树，按模块分组
    """
    service = PermissionService(session)
    tree = await service.get_permission_tree(
        current_user.tenant_id,
        permission_type
    )
    
    return ResponseBuilder.build_success(
        data=tree,
        message="获取权限树成功"
    )


@router.get("/user-tree")
async def get_user_permission_tree(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    获取当前用户的权限树（用于角色授权）
    
    只返回当前用户拥有的权限，用于角色授权时限制可分配的权限范围
    
    Returns:
        当前用户拥有的权限树
    """
    logger.info(f"获取用户权限树: user_id={current_user.id}, tenant_id={current_user.tenant_id}")
    
    service = PermissionService(session)
    tree = await service.get_user_permission_tree(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id
    )
    
    logger.info(f"返回权限树: count={len(tree)}")
    
    return ResponseBuilder.build_success(
        data=tree,
        message="获取用户权限树成功"
    )


@router.get("/check-children")
async def check_permission_children(
    id: UUID = Query(..., description="权限ID"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    检查权限是否有子权限
    
    权限：任何登录用户
    
    参数：
    - id: 权限ID（必填）
    
    返回格式：
    {
        "code": 200,
        "message": "查询成功",
        "data": {
            "has_children": true,
            "child_count": 5
        }
    }
    """
    from sqlalchemy import select, func
    from models.permission import Permission
    
    # 查询子权限数量
    stmt = select(func.count()).select_from(Permission).where(
        Permission.parent_id == id
    )
    child_count = await session.scalar(stmt) or 0
    
    return ResponseBuilder.build_success(
        data={
            "has_children": child_count > 0,
            "child_count": child_count
        },
        message="查询成功"
    )


# ==================== 操作接口 ====================

@router.post("/create", status_code=status.HTTP_201_CREATED, dependencies=[has_perms("settings:permissions:create")])
async def create_permission(
    data: PermissionCreate,
    current_user: User = Depends(get_current_active_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    创建权限
    
    权限要求：permission:create 或 admin
    
    请求体：
    {
        "code": "...",       // 必填，权限代码
        "name": "...",       // 必填，权限名称
        "type": "...",       // 必填，权限类型（menu/function/directory）
        "module": "...",     // 必填，所属模块
        "description": "...",// 可选，权限描述
        "status": 0,         // 可选，状态（0-正常，1-停用）
        "parent_id": "...",  // 可选，父菜单ID
        "path": "...",       // 可选，前端路由路径
        "icon": "...",       // 可选，菜单图标
        "component": "...",  // 可选，前端组件路径
        "sort_order": 0,     // 可选，排序顺序
        "is_hidden": false,  // 可选，是否隐藏
        "api_path": "...",   // 可选，API 路径
        "http_method": "..." // 可选，HTTP 方法
    }
    
    返回格式：
    {
        "code": 201,
        "message": "创建成功",
        "data": {...}
    }
    """
    permission = await permission_service.create_permission(
        data=data.model_dump(),
        tenant_id=current_user.tenant_id,
        current_user=current_user
    )
    
    return ResponseBuilder.build_success(
        data=PermissionRead.model_validate(permission).model_dump(),
        message="创建成功",
        http_status=201
    )


@router.post("/update", dependencies=[has_perms("settings:permissions:edit")])
async def update_permission(
    data: PermissionUpdate,
    current_user: User = Depends(get_current_active_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    更新权限
    
    权限要求：permission:update 或 admin
    
    请求体：
    {
        "id": "...",         // 必填，权限ID
        "code": "...",       // 可选，权限代码
        "name": "...",       // 可选，权限名称
        "type": "...",       // 可选，权限类型
        "module": "...",     // 可选，所属模块
        "description": "...",// 可选，权限描述
        "status": 0,         // 可选，状态（0-正常，1-停用）
        "parent_id": "...",  // 可选，父菜单ID
        "path": "...",       // 可选，前端路由路径
        "icon": "...",       // 可选，菜单图标
        "component": "...",  // 可选，前端组件路径
        "sort_order": 0,     // 可选，排序顺序
        "is_hidden": false,  // 可选，是否隐藏
        "api_path": "...",   // 可选，API 路径
        "http_method": "..." // 可选，HTTP 方法
    }
    
    返回格式：
    {
        "code": 200,
        "message": "更新成功",
        "data": {...}
    }
    
    注意：
    - 如果将状态改为停用（status=1），且该权限有子权限，则会同时停用所有子权限
    """
    permission = await permission_service.update_permission(
        permission_id=data.id,
        data=data.model_dump(exclude={'id'}, exclude_none=True),
        tenant_id=current_user.tenant_id,
        current_user=current_user
    )
    
    return ResponseBuilder.build_success(
        data=PermissionRead.model_validate(permission).model_dump(),
        message="更新成功"
    )


@router.post("/delete", dependencies=[has_perms("settings:permissions:delete")])
async def delete_permission(
    data: PermissionDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    删除权限（硬删除）
    
    权限要求：permission:delete 或 admin
    
    请求体：
    {
        "id": "..."  // 必填，权限ID
    }
    
    注意：
    - 如果权限已被角色使用，无法删除
    - 实际执行硬删除（从数据库中删除记录）
    
    返回格式：
    {
        "code": 200,
        "message": "删除成功",
        "data": {"id": "..."}
    }
    """
    await permission_service.delete_permission(
        permission_id=data.id,
        tenant_id=current_user.tenant_id
    )
    
    return ResponseBuilder.build_success(
        data={"id": str(data.id)},
        message="删除成功"
    )
