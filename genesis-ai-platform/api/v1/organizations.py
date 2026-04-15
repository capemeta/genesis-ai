"""
组织架构管理 API
职责：处理 HTTP 请求/响应，参数验证，调用 Service 层
"""
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from core.security import get_current_active_user
from core.security.permissions import has_perms
from core.response import ResponseBuilder
from schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationRead,
    OrganizationListResponse,
    OrganizationDeleteRequest
)
from models.organization import Organization
from models.user import User
from services.organization_service import OrganizationService

router = APIRouter()


def get_organization_service(db: AsyncSession = Depends(get_async_session)) -> OrganizationService:
    """获取组织服务实例"""
    return OrganizationService(model=Organization, db=db)


# ==================== 查询接口 ====================

@router.get("/list", dependencies=[has_perms("settings:organizations:query")])
async def list_organizations(
    name: str | None = Query(None, description="部门名称（模糊搜索）"),
    status: str | None = Query(None, description="状态过滤：0-正常，1-停用"),
    current_user: User = Depends(get_current_active_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """
    获取组织列表
    
    权限：任何登录用户
    返回扁平列表，前端构建树形结构
    
    参数：
    - name: 部门名称（模糊搜索）
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
    organizations = await org_service.list_organizations(
        tenant_id=current_user.tenant_id,
        name=name,
        status_filter=status
    )
    
    return ResponseBuilder.build_success(
        data={
            "data": [OrganizationListResponse.model_validate(org).model_dump() for org in organizations],
            "total": len(organizations)
        },
        message="查询成功"
    )


@router.get("/tree")
async def get_organization_tree(
    status: str | None = Query('0', description="状态过滤：0-正常，1-停用，空-全部"),
    current_user: User = Depends(get_current_active_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """
    获取组织树形结构
    
    权限：任何登录用户
    用于下拉选择器等场景
    
    参数：
    - status: 状态过滤，默认只获取正常状态
    
    返回格式：
    {
        "code": 200,
        "message": "查询成功",
        "data": [
            {
                "id": "...",
                "name": "...",
                "children": [...]
            }
        ]
    }
    """
    # 空字符串表示不过滤
    status_filter = status if status else None
    
    tree = await org_service.get_organization_tree(
        tenant_id=current_user.tenant_id,
        status_filter=status_filter
    )
    
    return ResponseBuilder.build_success(
        data=tree,
        message="查询成功"
    )


@router.get("/get", dependencies=[has_perms("settings:organizations:query")])
async def get_organization(
    id: UUID = Query(..., description="组织ID"),
    current_user: User = Depends(get_current_active_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """
    获取组织详情
    
    权限：任何登录用户
    
    参数：
    - id: 组织ID（必填）
    
    返回格式：
    {
        "code": 200,
        "message": "查询成功",
        "data": {...}
    }
    """
    org = await org_service.get_organization(
        org_id=id,
        tenant_id=current_user.tenant_id
    )
    
    return ResponseBuilder.build_success(
        data=OrganizationRead.model_validate(org).model_dump(),
        message="查询成功"
    )


# ==================== 操作接口 ====================

@router.post("/create", status_code=status.HTTP_201_CREATED, dependencies=[has_perms("settings:organizations:create")])
async def create_organization(
    data: OrganizationCreate,
    current_user: User = Depends(get_current_active_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """
    创建组织
    
    权限：任何登录用户（可根据需要添加权限控制）
    
    请求体：
    {
        "parent_id": "...",  // 可选，父部门ID
        "name": "...",       // 必填，部门名称
        "order_num": 10,     // 可选，排序号
        "status": "0",       // 可选，状态
        "leader_name": "...",// 可选，负责人
        "phone": "...",      // 可选，联系电话
        "email": "..."       // 可选，邮箱
    }
    
    返回格式：
    {
        "code": 201,
        "message": "创建成功",
        "data": {...}
    }
    """
    org = await org_service.create_organization(
        data=data,
        tenant_id=current_user.tenant_id,
        current_user=current_user
    )
    
    return ResponseBuilder.build_success(
        data=OrganizationRead.model_validate(org).model_dump(),
        message="创建成功",
        http_status=201
    )


@router.post("/update", dependencies=[has_perms("settings:organizations:edit")])
async def update_organization(
    data: OrganizationUpdate,
    current_user: User = Depends(get_current_active_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """
    更新组织
    
    权限：任何登录用户（可根据需要添加权限控制）
    
    请求体：
    {
        "id": "...",         // 必填，组织ID
        "parent_id": "...",  // 可选，父部门ID
        "name": "...",       // 可选，部门名称
        "order_num": 10,     // 可选，排序号
        "status": "0",       // 可选，状态
        "leader_name": "...",// 可选，负责人
        "phone": "...",      // 可选，联系电话
        "email": "..."       // 可选，邮箱
    }
    
    注意：
    - 修改父部门时会校验循环引用
    - 修改父部门时会自动更新所有子部门的路径
    
    返回格式：
    {
        "code": 200,
        "message": "更新成功",
        "data": {...}
    }
    """
    org = await org_service.update_organization(
        data=data,
        tenant_id=current_user.tenant_id,
        current_user=current_user
    )
    
    return ResponseBuilder.build_success(
        data=OrganizationRead.model_validate(org).model_dump(),
        message="更新成功"
    )


@router.post("/delete", dependencies=[has_perms("settings:organizations:delete")])
async def delete_organization(
    data: OrganizationDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """
    删除组织（软删除）
    
    权限：任何登录用户（可根据需要添加权限控制）
    
    请求体：
    {
        "id": "..."  // 必填，组织ID
    }
    
    注意：
    - 如果存在子部门，无法删除
    - 如果存在关联用户，无法删除
    - 实际执行软删除（设置 del_flag='1'）
    
    返回格式：
    {
        "code": 200,
        "message": "删除成功",
        "data": {"id": "..."}
    }
    """
    await org_service.delete_organization(
        org_id=data.id,
        tenant_id=current_user.tenant_id,
        current_user=current_user
    )
    
    return ResponseBuilder.build_success(
        data={"id": str(data.id)},
        message="删除成功"
    )
