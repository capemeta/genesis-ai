"""
基础 Router 工厂
自动生成标准的 CRUD 路由，符合 Refine 规范
"""
from typing import Type, Callable, Optional, List, Any, Sequence, cast
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, create_model
from enum import Enum

from core.database import get_async_session
from core.security import get_current_active_user
from core.response import ResponseBuilder, refine_delete_response
from core.base_service import BaseService
from models.user import User
from schemas.common import ListRequest


def create_crud_router(
    model_class: Type,
    service_class: Type[BaseService],
    read_schema: Type[BaseModel],
    create_schema: Type[BaseModel],
    update_schema: Type[BaseModel],
    prefix: str = "",
    tags: Optional[Sequence[str]] = None,
    get_db: Callable = get_async_session,
    get_current_user: Callable = get_current_active_user,
    list_request_schema: Type[ListRequest] = ListRequest,
    enable_list: bool = True,
    enable_get: bool = True,
    enable_create: bool = True,
    enable_update: bool = True,
    enable_delete: bool = True,
    # 权限控制参数
    list_permissions: Optional[List[str]] = None,
    get_permissions: Optional[List[str]] = None,
    create_permissions: Optional[List[str]] = None,
    update_permissions: Optional[List[str]] = None,
    delete_permissions: Optional[List[str]] = None,
) -> APIRouter:
    """
    创建标准 CRUD 路由
    
    该工厂会自动生成纯 POST Action 风格的路由系统（避免路径中的业务 ID）:
       - POST   /list            -> 列表 (支持分页/过滤/排序对象)
       - POST   /get             -> 获取 (Body: {"id": "..."})
       - POST   /create          -> 创建
       - POST   /update          -> 更新 (Body: {"id": "...", ...})
       - POST   /delete          -> 删除 (Body: {"id": "..."})
    
    使用示例：
    
    router = create_crud_router(
        model_class=KnowledgeBase,
        service_class=KnowledgeBaseService,
        read_schema=KnowledgeBaseRead,
        create_schema=KnowledgeBaseCreate,
        update_schema=KnowledgeBaseUpdate,
        prefix="/knowledge-bases",
        tags=["knowledge-bases"],
        # 权限控制
        list_permissions=["kb:read", "admin"],
        create_permissions=["kb:write", "admin"],
    )
    
    Args:
        model_class: SQLAlchemy 模型类
        service_class: Service 类
        read_schema: 读取响应 Schema
        create_schema: 创建请求 Schema
        update_schema: 更新请求 Schema
        prefix: 路由前缀
        tags: OpenAPI 标签
        get_db: 获取数据库会话的依赖
        get_current_user: 获取当前用户的依赖
        list_request_schema: 列表请求 Schema (可选，默认为通用 ListRequest)
        enable_*: 是否启用对应的路由组
        *_permissions: 各操作所需的权限列表（可选）
        
    Returns:
        配置好的 APIRouter
    """
    router_tags: List[str | Enum] = list(tags) if tags else [prefix.strip("/")]
    router = APIRouter(prefix=prefix, tags=router_tags)
    
    # 🔥 动态检测模型的 ID 类型（支持 UUID 和 int）
    id_type: type[Any] = UUID  # 默认使用 UUID
    if hasattr(model_class, '__annotations__') and 'id' in model_class.__annotations__:
        id_annotation = model_class.__annotations__['id']
        # 检查是否是 Mapped[int]
        if hasattr(id_annotation, '__origin__'):
            # 处理 Mapped[int] 这种泛型类型
            args = getattr(id_annotation, '__args__', ())
            if args and args[0] == int:
                id_type = int
        elif id_annotation == int:
            id_type = int
    
    # 动态创建 ItemIdRequest（支持不同的 ID 类型）
    DynamicItemIdRequest = cast(
        type[BaseModel],
        create_model(
        f"{model_class.__name__}ItemIdRequest",
        id=(id_type, ...)
        ),
    )
    
    def get_service(db: AsyncSession = Depends(get_db)) -> BaseService:
        """获取服务实例"""
        return service_class(model=model_class, db=db)
    
    # 根据权限配置动态创建依赖
    def get_user_dependency(permissions: Optional[List[str]] = None):
        """根据权限要求返回对应的用户依赖"""
        if permissions:
            # 如果指定了权限，使用 require_permissions
            from core.security import require_permissions
            return require_permissions(*permissions)
        else:
            # 否则只需要登录用户
            return get_current_user
    
    # ==================== 列表接口 ====================
    if enable_list:
        async def _handle_list(
            params: ListRequest,
            current_user: User,
            service: BaseService,
        ):
            """处理列表逻辑的内部函数"""
            resources, total = await service.list_resources(
                tenant_id=current_user.tenant_id,
                page=params.get_page(),
                page_size=params.get_page_size(),
                search=params.get_search(),
                filters=params.filters,
                advanced_filters=params.advanced_filters,
                order_by=params.get_order_by() or "created_at desc",
                user_id=current_user.id
            )
            
            # 转换为响应 Schema
            data = [read_schema.model_validate(r).model_dump(by_alias=True) for r in resources]
            
            return ResponseBuilder.build_success(
                data={"data": data, "total": total},
                message="获取列表成功"
            )

        # POST 路由 (Action 风格)
        @router.post("/list", response_model=dict)
        async def list_resources_post(
            request: list_request_schema,  # type: ignore[valid-type]
            current_user: User = Depends(get_user_dependency(list_permissions)),
            service: BaseService = Depends(get_service),
        ):
            """获取资源列表 (POST)"""
            return await _handle_list(cast(ListRequest, request), current_user, service)
    
    # ==================== 获取单个资源 ====================
    if enable_get:
        async def _handle_get(
            resource_id,  # 不指定类型，支持 UUID 和 int
            current_user: User,
            service: BaseService,
        ):
            resource = await service.get_by_id(
                resource_id=resource_id,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id
            )
            return ResponseBuilder.build_success(
                data=read_schema.model_validate(resource).model_dump(by_alias=True),
                message="获取详情成功"
            )

        # POST 路由
        @router.post("/get", response_model=dict)
        async def get_resource_post(
            request: DynamicItemIdRequest,  # type: ignore[valid-type]
            current_user: User = Depends(get_user_dependency(get_permissions)),
            service: BaseService = Depends(get_service),
        ):
            return await _handle_get(getattr(request, "id"), current_user, service)
    
    # ==================== 创建资源 ====================
    if enable_create:
        async def _handle_create(
            data: BaseModel,
            current_user: User,
            service: BaseService,
        ):
            resource = await service.create(data=data, current_user=current_user)
            return ResponseBuilder.build_success(
                data=read_schema.model_validate(resource).model_dump(by_alias=True),
                message="创建成功",
                http_status=201
            )

        # POST /create
        @router.post("/create", response_model=dict, status_code=status.HTTP_201_CREATED)
        async def create_resource_action(
            data: create_schema,  # type: ignore[valid-type]
            current_user: User = Depends(get_user_dependency(create_permissions)),
            service: BaseService = Depends(get_service),
        ):
            return await _handle_create(data, current_user, service)
    
    # ==================== 更新资源 ====================
    if enable_update:
        async def _handle_update(
            resource_id,  # 不指定类型，支持 UUID 和 int
            data: BaseModel,
            current_user: User,
            service: BaseService,
        ):
            resource = await service.update(
                resource_id=resource_id,
                data=data,
                current_user=current_user
            )
            return ResponseBuilder.build_success(
                data=read_schema.model_validate(resource).model_dump(by_alias=True),
                message="更新成功"
            )

        # POST /update (Action 风格)
        # 为支持 POST /update，我们需要一个组合了 ID 和数据的 Schema
        dynamic_update_schema = cast(
            type[BaseModel],
            create_model(
                f"{update_schema.__name__}WithId",
                id=(id_type, ...),
                __base__=update_schema
            ),
        )

        @router.post("/update", response_model=dict)
        async def update_resource_post(
            request: dynamic_update_schema,  # type: ignore[valid-type]
            current_user: User = Depends(get_user_dependency(update_permissions)),
            service: BaseService = Depends(get_service),
        ):
            # 🔥 使用 exclude_unset=True 只提取客户端实际传递的字段
            update_data = cast(Any, request).model_dump(exclude_unset=True, exclude={"id"})
            # 注意：service.update 期望的是 update_schema 实例
            data_obj = update_schema(**update_data)
            return await _handle_update(getattr(request, "id"), data_obj, current_user, service)
    
    # ==================== 删除资源 ====================
    if enable_delete:
        async def _handle_delete(
            resource_id,  # 不指定类型，支持 UUID 和 int
            current_user: User,
            service: BaseService,
        ):
            await service.delete(resource_id=resource_id, current_user=current_user)
            return ResponseBuilder.build_success(
                data={"id": str(resource_id)},
                message="删除成功"
            )

        # POST /delete
        @router.post("/delete", response_model=dict)
        async def delete_resource_post(
            request: DynamicItemIdRequest,  # type: ignore[valid-type]
            current_user: User = Depends(get_user_dependency(delete_permissions)),
            service: BaseService = Depends(get_service),
        ):
            return await _handle_delete(getattr(request, "id"), current_user, service)
    
    return router
