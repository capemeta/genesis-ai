"""
基础 Service 类
提供通用的 CRUD 操作，自动处理租户隔离、权限检查等
"""
from typing import Generic, TypeVar, Type, List, Tuple, Optional, Any, Dict, cast
from uuid import UUID
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from fastapi import HTTPException, status

from models.user import User

ModelType = TypeVar("ModelType", bound=DeclarativeBase)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    基础服务类，提供通用 CRUD 操作
    
    使用示例：
    
    class KnowledgeBaseService(BaseService[KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate]):
        pass
    
    # 自动获得以下方法：
    # - list_resources(tenant_id, page, page_size, filters, order_by) -> (List[Model], int)
    # - get_by_id(resource_id, tenant_id) -> Model
    # - create(data, current_user) -> Model
    # - update(resource_id, data, current_user) -> Model
    # - delete(resource_id, current_user) -> None
    """
    
    def __init__(
        self,
        model: Type[ModelType],
        db: AsyncSession,
        resource_name: Optional[str] = None
    ):
        """
        初始化服务
        
        Args:
            model: SQLAlchemy 模型类
            db: 数据库会话
            resource_name: 资源名称（用于错误消息）
        """
        self.model = model
        self.db = db
        self.resource_name = resource_name or model.__tablename__
    
    async def list_resources(
        self,
        tenant_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        advanced_filters: Optional[List[Any]] = None,
        order_by: str = "created_at desc",
        user_id: Optional[UUID] = None,
        include_public: bool = True
    ) -> Tuple[List[ModelType], int]:
        """
        获取资源列表（带分页）
        
        Args:
            tenant_id: 租户 ID（可选，如果模型没有 tenant_id 字段则忽略）
            page: 页码（从 1 开始）
            page_size: 每页数量
            search: 简单搜索（模糊匹配，搜索模型定义的 __searchable_fields__）
            filters: 精确过滤（字典格式，精确匹配）
            advanced_filters: 高级过滤（列表格式，支持操作符）
                格式: [{"field": "name", "op": "like", "value": "test"}]
                支持的操作符: eq, ne, gt, gte, lt, lte, like, in, not_in, is_null, is_not_null
            order_by: 排序字段
            user_id: 用户 ID（用于权限过滤）
            include_public: 是否包含公开资源
            
        Returns:
            (资源列表, 总数)
        """
        # 基础查询条件：租户隔离（如果模型有 tenant_id 字段）
        model_cls = cast(Any, self.model)
        conditions: List[Any] = []
        if hasattr(self.model, "tenant_id") and tenant_id is not None:
            conditions.append(model_cls.tenant_id == tenant_id)
        
        # 软删除过滤
        if hasattr(self.model, "deleted_at"):
            conditions.append(model_cls.deleted_at.is_(None))
        
        # 权限过滤（如果模型有 owner_id 和 visibility）
        if user_id and hasattr(self.model, "owner_id") and hasattr(self.model, "visibility"):
            if include_public:
                conditions.append(
                    or_(
                        model_cls.owner_id == user_id,
                        model_cls.visibility == "tenant_public"
                    )
                )
            else:
                conditions.append(model_cls.owner_id == user_id)
        
        # 1. 简单搜索（模糊匹配）
        if search:
            # 获取模型定义的可搜索字段（默认为 ["name"]）
            searchable_fields = cast(List[str], getattr(self.model, "__searchable_fields__", ["name"]))
            search_conditions: List[Any] = []
            
            for field_name in searchable_fields:
                if hasattr(self.model, field_name):
                    field = getattr(self.model, field_name)
                    search_conditions.append(field.ilike(f"%{search}%"))
            
            if search_conditions:
                conditions.append(or_(*search_conditions))
        
        # 2. 精确过滤（字典格式）
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    conditions.append(getattr(self.model, field) == value)
        
        # 3. 高级过滤（支持操作符）
        if advanced_filters:
            for filter_item in advanced_filters:
                filter_field_name: Optional[str]
                filter_op: Any
                filter_value: Any
                # 兼容 dict 与 Pydantic 模型（如 AdvancedFilter）
                # 避免把模型对象当 dict 调用 .get 导致 AttributeError
                if isinstance(filter_item, dict):
                    raw_field_name = filter_item.get("field")
                    filter_field_name = str(raw_field_name).strip() if raw_field_name is not None else None
                    filter_op = filter_item.get("op", "eq")
                    filter_value = filter_item.get("value")
                else:
                    raw_field_name = getattr(filter_item, "field", None)
                    filter_field_name = str(raw_field_name).strip() if raw_field_name is not None else None
                    filter_op = getattr(filter_item, "op", "eq")
                    filter_value = getattr(filter_item, "value", None)

                # 兼容 Enum 操作符，统一转成字符串
                filter_op = filter_op.value if hasattr(filter_op, "value") else filter_op
                
                if not filter_field_name or not hasattr(self.model, filter_field_name):
                    continue
                
                field = getattr(self.model, filter_field_name)
                
                # 应用操作符
                if filter_op == "eq":
                    conditions.append(field == filter_value)
                elif filter_op == "ne":
                    conditions.append(field != filter_value)
                elif filter_op == "gt":
                    conditions.append(field > filter_value)
                elif filter_op == "gte":
                    conditions.append(field >= filter_value)
                elif filter_op == "lt":
                    conditions.append(field < filter_value)
                elif filter_op == "lte":
                    conditions.append(field <= filter_value)
                elif filter_op == "like":
                    conditions.append(field.ilike(f"%{filter_value}%"))
                elif filter_op == "in":
                    if isinstance(filter_value, list):
                        conditions.append(field.in_(filter_value))
                elif filter_op == "not_in":
                    if isinstance(filter_value, list):
                        conditions.append(~field.in_(filter_value))
                elif filter_op == "is_null":
                    conditions.append(field.is_(None))
                elif filter_op == "is_not_null":
                    conditions.append(field.isnot(None))
        
        # 计算总数
        count_stmt = select(func.count()).select_from(self.model).where(*conditions)
        total = await self.db.scalar(count_stmt) or 0
        
        # 分页查询
        offset = (page - 1) * page_size
        stmt = select(self.model).where(*conditions).offset(offset).limit(page_size)
        
        # 排序
        if order_by:
            # 简单处理：支持 "field asc" 或 "field desc"
            parts = order_by.split()
            if len(parts) == 2:
                field, direction = parts
                if hasattr(self.model, field):
                    order_col = getattr(self.model, field)
                    stmt = stmt.order_by(order_col.desc() if direction.lower() == "desc" else order_col.asc())
            elif len(parts) == 1 and hasattr(self.model, parts[0]):
                stmt = stmt.order_by(getattr(self.model, parts[0]))
        
        result = await self.db.execute(stmt)
        resources = result.scalars().all()
        
        return list(resources), total
    
    async def get_by_id(
        self,
        resource_id: UUID,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        check_permission: bool = True
    ) -> ModelType:
        """
        根据 ID 获取资源
        
        Args:
            resource_id: 资源 ID
            tenant_id: 租户 ID（可选，如果模型没有 tenant_id 字段则忽略）
            user_id: 用户 ID（用于权限检查）
            check_permission: 是否检查权限
            
        Returns:
            资源对象
            
        Raises:
            HTTPException: 404 资源不存在，403 无权限
        """
        # 构建查询条件
        model_cls = cast(Any, self.model)
        conditions: List[Any] = [model_cls.id == resource_id]
        
        # 租户隔离（如果模型有 tenant_id 字段）
        if hasattr(self.model, "tenant_id") and tenant_id is not None:
            conditions.append(model_cls.tenant_id == tenant_id)
        
        stmt = select(self.model).where(*conditions)
        
        # 软删除过滤
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(model_cls.deleted_at.is_(None))
        
        result = await self.db.execute(stmt)
        resource = result.scalar_one_or_none()
        
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.resource_name.capitalize()} not found"
            )
        
        # 权限检查
        if check_permission and user_id and hasattr(resource, "owner_id"):
            if resource.owner_id != user_id:
                # 检查是否是公开资源
                if hasattr(resource, "visibility") and resource.visibility != "tenant_public":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"You don't have permission to access this {self.resource_name}"
                    )
        
        return resource
    
    async def create(
        self,
        data: CreateSchemaType,
        current_user: Optional[User] = None
    ) -> ModelType:
        """
        创建资源
        
        Args:
            data: 创建数据
            current_user: 当前用户（可选，某些场景可能不需要登录）
            
        Returns:
            创建的资源对象
        """
        # 转换为字典
        create_data: Dict[str, Any]
        if isinstance(data, dict):
            create_data = dict(data)
        elif hasattr(data, "model_dump"):
            create_data = cast(Dict[str, Any], data.model_dump())
        else:
            create_data = cast(Dict[str, Any], cast(Any, data).dict())
        
        # 智能填充审计字段（优先使用传递的值，未传递时才自动填充）
        if current_user:
            # 租户隔离（如果模型有 tenant_id 字段且未传递）
            if hasattr(self.model, "tenant_id") and "tenant_id" not in create_data:
                if hasattr(current_user, "tenant_id"):
                    create_data["tenant_id"] = current_user.tenant_id
            
            # 所有者（如果模型有 owner_id 字段且未传递）
            if hasattr(self.model, "owner_id") and "owner_id" not in create_data:
                if hasattr(current_user, "id"):
                    create_data["owner_id"] = current_user.id
            
            # 创建人 ID（如果模型有 created_by_id 字段且未传递）
            if hasattr(self.model, "created_by_id") and "created_by_id" not in create_data:
                if hasattr(current_user, "id"):
                    create_data["created_by_id"] = current_user.id
            
            # 创建人名称（如果模型有 created_by_name 字段且未传递）
            if hasattr(self.model, "created_by_name") and "created_by_name" not in create_data:
                # 优先使用 nickname，其次 username，都没有则使用 "System"
                if hasattr(current_user, "nickname") and current_user.nickname:
                    create_data["created_by_name"] = current_user.nickname
                elif hasattr(current_user, "username") and current_user.username:
                    create_data["created_by_name"] = current_user.username
                else:
                    create_data["created_by_name"] = "System"
        
        # 创建时间（如果模型有 created_at 字段且未传递）
        if hasattr(self.model, "created_at") and "created_at" not in create_data:
            from datetime import datetime, timezone
            # 使用带时区的当前时间（数据库会自动转换为其时区）
            create_data["created_at"] = datetime.now(timezone.utc)
        
        # 更新时间（如果模型有 updated_at 字段且未传递）
        if hasattr(self.model, "updated_at") and "updated_at" not in create_data:
            from datetime import datetime, timezone
            create_data["updated_at"] = datetime.now(timezone.utc)
        
        # 创建对象
        resource = self.model(**create_data)
        self.db.add(resource)
        await self.db.commit()
        await self.db.refresh(resource)
        
        return resource
    
    async def update(
        self,
        resource_id: UUID,
        data: UpdateSchemaType,
        current_user: Optional[User] = None
    ) -> ModelType:
        """
        更新资源
        
        Args:
            resource_id: 资源 ID
            data: 更新数据
            current_user: 当前用户（可选）
            
        Returns:
            更新后的资源对象
        """
        # 获取资源（自动检查权限）
        resource = await self.get_by_id(
            resource_id,
            current_user.tenant_id if current_user and hasattr(current_user, "tenant_id") else None,
            current_user.id if current_user and hasattr(current_user, "id") else None,
            check_permission=True if current_user else False
        )
        
        # 转换为字典，排除未设置的字段
        update_data: Dict[str, Any]
        if isinstance(data, dict):
            update_data = dict(data)
        elif hasattr(data, "model_dump"):
            update_data = cast(Dict[str, Any], data.model_dump(exclude_unset=True))
        else:
            update_data = cast(Dict[str, Any], cast(Any, data).dict(exclude_unset=True))
        
        # 智能填充审计字段（优先使用传递的值，未传递时才自动填充）
        if current_user:
            # 更新人 ID（如果模型有 updated_by_id 字段且未传递）
            if hasattr(self.model, "updated_by_id") and "updated_by_id" not in update_data:
                if hasattr(current_user, "id"):
                    update_data["updated_by_id"] = current_user.id
            
            # 更新人名称（如果模型有 updated_by_name 字段且未传递）
            if hasattr(self.model, "updated_by_name") and "updated_by_name" not in update_data:
                # 优先使用 nickname，其次 username，都没有则使用 "System"
                if hasattr(current_user, "nickname") and current_user.nickname:
                    update_data["updated_by_name"] = current_user.nickname
                elif hasattr(current_user, "username") and current_user.username:
                    update_data["updated_by_name"] = current_user.username
                else:
                    update_data["updated_by_name"] = "System"
        # 更新时间（如果模型有 updated_at 字段且未传递）
        if hasattr(self.model, "updated_at") and "updated_at" not in update_data:
            from datetime import datetime, timezone
            update_data["updated_at"] = datetime.now(timezone.utc)
        
        # 更新字段
        for field, value in update_data.items():
            if hasattr(resource, field):
                setattr(resource, field, value)
        
        await self.db.commit()
        await self.db.refresh(resource)
        
        return resource
    
    async def delete(
        self,
        resource_id: UUID,
        current_user: Optional[User] = None,
        soft_delete: bool = True
    ) -> None:
        """
        删除资源
        
        Args:
            resource_id: 资源 ID
            current_user: 当前用户（可选）
            soft_delete: 是否软删除（如果模型支持）
        """
        # 获取资源（自动检查权限）
        resource = await self.get_by_id(
            resource_id,
            current_user.tenant_id if current_user and hasattr(current_user, "tenant_id") else None,
            current_user.id if current_user and hasattr(current_user, "id") else None,
            check_permission=True if current_user else False
        )
        
        # 软删除
        if soft_delete and hasattr(self.model, "deleted_at"):
            resource_obj = cast(Any, resource)
            from datetime import datetime, timezone
            
            # 设置删除时间（使用带时区的当前时间）
            if not hasattr(resource_obj, "deleted_at") or resource_obj.deleted_at is None:
                resource_obj.deleted_at = datetime.now(timezone.utc)
            
            # 记录删除人信息（如果字段存在且有当前用户，且未手动设置）
            if current_user:
                if hasattr(resource_obj, "updated_by_id") and resource_obj.updated_by_id is None:
                    if hasattr(current_user, "id"):
                        resource_obj.updated_by_id = current_user.id
                
                if hasattr(resource, "updated_by_name") and (not hasattr(resource, "updated_by_name") or resource.updated_by_name is None):
                    if hasattr(current_user, "nickname") and current_user.nickname:
                        resource.updated_by_name = current_user.nickname
                    elif hasattr(current_user, "username") and current_user.username:
                        resource.updated_by_name = current_user.username
                    else:
                        resource.updated_by_name = "System"
                
                if hasattr(resource, "updated_at"):
                    resource.updated_at = datetime.now(timezone.utc)
            
            await self.db.commit()
        else:
            # 硬删除
            await self.db.delete(resource)
            await self.db.commit()
