"""
CRUD 工厂 - 自动化 CRUD 生成
只需注册模型，自动生成完整的 Service、Router、Schema
"""
from typing import Type, Optional, List, Dict, Any
from pydantic import BaseModel, create_model
from sqlalchemy.orm import DeclarativeBase
from fastapi import APIRouter

from core.base_service import BaseService
from core.base_router import create_crud_router
from schemas.common import ListRequest


class CRUDFactory:
    """
    CRUD 工厂类
    
    使用示例：
    
    # 1. 注册模型（自动生成 Schema、Service、Router）
    crud_factory.register(
        model=KnowledgeBase,
        prefix="/knowledge-bases",
        tags=["knowledge-bases"]
    )
    
    # 2. 获取 Router 并注册到 FastAPI
    app.include_router(crud_factory.get_router("KnowledgeBase"))
    
    # 完成！自动拥有完整 CRUD 功能
    """
    
    def __init__(self):
        self._registered_models: Dict[str, Dict[str, Any]] = {}
        self._routers: Dict[str, APIRouter] = {}
        self._services: Dict[str, Type[BaseService]] = {}
    
    def register(
        self,
        model: Type[DeclarativeBase],
        prefix: str,
        tags: Optional[List[str]] = None,
        create_schema: Optional[Type[BaseModel]] = None,
        update_schema: Optional[Type[BaseModel]] = None,
        read_schema: Optional[Type[BaseModel]] = None,
        list_request_schema: Optional[Type[ListRequest]] = None,
        service_class: Optional[Type[BaseService]] = None,
        enable_list: bool = True,
        enable_get: bool = True,
        enable_create: bool = True,
        enable_update: bool = True,
        enable_delete: bool = True,
        exclude_fields: Optional[List[str]] = None,
        readonly_fields: Optional[List[str]] = None,
        # 权限控制参数
        list_permissions: Optional[List[str]] = None,
        get_permissions: Optional[List[str]] = None,
        create_permissions: Optional[List[str]] = None,
        update_permissions: Optional[List[str]] = None,
        delete_permissions: Optional[List[str]] = None,
    ) -> APIRouter:
        """
        注册模型，自动生成 CRUD
        
        Args:
            model: SQLAlchemy 模型类
            prefix: 路由前缀（如 "/knowledge-bases"）
            tags: OpenAPI 标签
            create_schema: 自定义创建 Schema（可选，不提供则自动生成）
            update_schema: 自定义更新 Schema（可选，不提供则自动生成）
            read_schema: 自定义读取 Schema（可选，不提供则自动生成）
            service_class: 自定义 Service 类（可选，不提供则使用 BaseService）
            enable_*: 是否启用对应的路由
            exclude_fields: 排除的字段（不在 Schema 中显示）
            readonly_fields: 只读字段（不能在 create/update 中修改）
            *_permissions: 各操作所需的权限列表（可选）
                - 如果不提供，只需要登录用户
                - 如果提供，会自动检查用户是否拥有这些权限之一
                - 示例：["kb:read", "admin"] 表示需要 kb:read 或 admin 权限
            
        Returns:
            生成的 APIRouter
        """
        model_name = model.__name__
        
        # 自动生成 Schema（如果未提供）
        if not read_schema:
            read_schema = self._generate_read_schema(model, exclude_fields)
        
        if not create_schema:
            create_schema = self._generate_create_schema(model, exclude_fields, readonly_fields)
        
        if not update_schema:
            update_schema = self._generate_update_schema(model, exclude_fields, readonly_fields)
        
        # 自动生成 Service（如果未提供）
        if not service_class:
            service_class = type(
                f"{model_name}Service",
                (BaseService,),
                {}
            )
        
        # 创建 Router
        router = create_crud_router(
            model_class=model,
            service_class=service_class,
            read_schema=read_schema,
            create_schema=create_schema,
            update_schema=update_schema,
            list_request_schema=list_request_schema or ListRequest,
            prefix=prefix,
            tags=tags or [prefix.strip("/")],
            enable_list=enable_list,
            enable_get=enable_get,
            enable_create=enable_create,
            enable_update=enable_update,
            enable_delete=enable_delete,
            # 传递权限配置
            list_permissions=list_permissions,
            get_permissions=get_permissions,
            create_permissions=create_permissions,
            update_permissions=update_permissions,
            delete_permissions=delete_permissions,
        )
        
        # 保存注册信息
        self._registered_models[model_name] = {
            "model": model,
            "prefix": prefix,
            "tags": tags,
            "read_schema": read_schema,
            "create_schema": create_schema,
            "update_schema": update_schema,
            "service_class": service_class,
        }
        self._routers[model_name] = router
        self._services[model_name] = service_class
        
        return router
    
    def get_router(self, model_name: str) -> APIRouter:
        """获取已注册模型的 Router"""
        if model_name not in self._routers:
            raise ValueError(f"Model {model_name} not registered")
        return self._routers[model_name]
    
    def get_service(self, model_name: str) -> Type[BaseService]:
        """获取已注册模型的 Service 类"""
        if model_name not in self._services:
            raise ValueError(f"Model {model_name} not registered")
        return self._services[model_name]
    
    def get_all_routers(self) -> List[APIRouter]:
        """获取所有已注册的 Router"""
        return list(self._routers.values())
    
    def _generate_read_schema(
        self,
        model: Type[DeclarativeBase],
        exclude_fields: Optional[List[str]] = None
    ) -> Type[BaseModel]:
        """自动生成读取 Schema"""
        exclude_fields = exclude_fields or []
        
        # 默认排除的字段
        default_exclude = ["deleted_at", "hashed_password", "password"]
        exclude_fields.extend(default_exclude)
        
        fields = {}
        for column in model.__table__.columns:
            if column.name not in exclude_fields:
                # 获取 Python 类型
                python_type = column.type.python_type
                
                # 处理可空字段
                if column.nullable:
                    python_type = Optional[python_type]
                
                fields[column.name] = (python_type, ...)
        
        # 创建 Pydantic 模型（Pydantic v2）
        # 使用 __base__ 参数传递配置
        class ConfiguredBase(BaseModel):
            model_config = {"from_attributes": True}
        
        schema = create_model(
            f"{model.__name__}Read",
            __base__=ConfiguredBase,
            **fields
        )
        
        return schema
    
    def _generate_create_schema(
        self,
        model: Type[DeclarativeBase],
        exclude_fields: Optional[List[str]] = None,
        readonly_fields: Optional[List[str]] = None
    ) -> Type[BaseModel]:
        """自动生成创建 Schema"""
        exclude_fields = exclude_fields or []
        readonly_fields = readonly_fields or []
        
        # 默认排除的字段（自动生成或系统字段）
        default_exclude = [
            "id", "tenant_id", "owner_id",
            "created_at", "updated_at", "deleted_at",
            "created_by_id", "created_by_name",
            "updated_by_id", "updated_by_name",
            "hashed_password", "password"
        ]
        exclude_fields.extend(default_exclude)
        exclude_fields.extend(readonly_fields)
        
        fields = {}
        for column in model.__table__.columns:
            if column.name not in exclude_fields:
                python_type = column.type.python_type
                
                # 创建时，所有字段都可以为空（除非有默认值）
                if column.nullable or column.default is not None:
                    python_type = Optional[python_type]
                    fields[column.name] = (python_type, None)
                else:
                    fields[column.name] = (python_type, ...)
        
        schema = create_model(f"{model.__name__}Create", **fields)
        return schema
    
    def _generate_update_schema(
        self,
        model: Type[DeclarativeBase],
        exclude_fields: Optional[List[str]] = None,
        readonly_fields: Optional[List[str]] = None
    ) -> Type[BaseModel]:
        """自动生成更新 Schema"""
        exclude_fields = exclude_fields or []
        readonly_fields = readonly_fields or []
        
        # 默认排除的字段
        default_exclude = [
            "id", "tenant_id", "owner_id",
            "created_at", "updated_at", "deleted_at",
            "created_by_id", "created_by_name",
            "updated_by_id", "updated_by_name",
            "hashed_password", "password"
        ]
        exclude_fields.extend(default_exclude)
        exclude_fields.extend(readonly_fields)
        
        fields = {}
        for column in model.__table__.columns:
            if column.name not in exclude_fields:
                python_type = column.type.python_type
                
                # 更新时，所有字段都是可选的
                fields[column.name] = (Optional[python_type], None)
        
        schema = create_model(f"{model.__name__}Update", **fields)
        return schema


# 全局单例
crud_factory = CRUDFactory()
