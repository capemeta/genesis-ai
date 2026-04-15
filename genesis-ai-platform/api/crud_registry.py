"""
CRUD 注册中心
在这里集中注册所有需要标准 CRUD 的模型
"""
from core.crud_factory import crud_factory

# 导入所有需要 CRUD 的模型
from models.tenant import Tenant
from models.user import User
from models.knowledge_base import KnowledgeBase
from models.role import Role
from models.permission import Permission
# from models.document import Document
# from models.folder import Folder
# from models.tag import Tag
from models.folder import Folder
from models.tag import Tag
from models.document import Document
from models.knowledge_base_document import KnowledgeBaseDocument
from models.kb_glossary import KBGlossary
from models.kb_synonym import KBSynonym
from models.kb_synonym_variant import KBSynonymVariant
from models.task import Task
from models.chunk import Chunk
from models.model_provider_definition import ModelProviderDefinition
from models.tenant_model_provider import TenantModelProvider
from models.tenant_model_provider_credential import TenantModelProviderCredential
from models.platform_model import PlatformModel
from models.tenant_model import TenantModel
from models.tenant_default_model import TenantDefaultModel
from models.model_adapter_binding import ModelAdapterBinding

from services.tenant_service import TenantService
from services.knowledge_base_service import KnowledgeBaseService
from services.folder_service import FolderService
from services.tag_service import TagService
from services.document_service import DocumentService, KBDocumentService
from services.dictionary_service import KBGlossaryService, KBSynonymService, KBSynonymVariantService
from services.task_service import TaskService
from services.chunk_service import ChunkService
from services.model_platform_service import (
    ModelAdapterBindingService,
    ModelProviderDefinitionService,
    PlatformModelService,
    TenantDefaultModelService,
    TenantModelProviderCredentialService,
    TenantModelProviderService,
    TenantModelService,
)

from schemas.tenant import TenantCreate, TenantUpdate, TenantResponse, TenantListRequest
from schemas.user import UserCreate, UserUpdate, UserRead
from schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseRead
from schemas.folder import FolderCreate, FolderUpdate, FolderRead
from schemas.tag import TagCreate, TagUpdate, TagRead
from schemas.dictionary import (
    KBGlossaryCreate,
    KBGlossaryRead,
    KBGlossaryUpdate,
    KBSynonymCreate,
    KBSynonymRead,
    KBSynonymUpdate,
    KBSynonymVariantCreate,
    KBSynonymVariantRead,
    KBSynonymVariantUpdate,
)
from schemas.document import (
    DocumentRead, KBDocumentCreate, KBDocumentUpdate, KBDocumentRead, KBDocumentListRequest
)
from schemas.task import TaskCreate, TaskUpdate, TaskRead, TaskListRequest
from schemas.chunk import ChunkCreate, ChunkUpdate, ChunkRead, ChunkListRequest
from schemas.model_platform import (
    ModelAdapterBindingCreate,
    ModelAdapterBindingRead,
    ModelAdapterBindingUpdate,
    ModelPlatformListRequest,
    ModelProviderDefinitionCreate,
    ModelProviderDefinitionRead,
    ModelProviderDefinitionUpdate,
    PlatformModelCreate,
    PlatformModelRead,
    PlatformModelUpdate,
    TenantDefaultModelCreate,
    TenantDefaultModelRead,
    TenantDefaultModelUpdate,
    TenantModelCreate,
    TenantModelProviderCreate,
    TenantModelProviderCredentialCreate,
    TenantModelProviderCredentialRead,
    TenantModelProviderCredentialUpdate,
    TenantModelProviderRead,
    TenantModelProviderUpdate,
    TenantModelRead,
    TenantModelUpdate,
)


def register_all_crud():
    """
    注册所有 CRUD 路由
    
    新增表时，只需在这里添加一行注册代码即可！
    """
    
    # ==================== 租户（管理员专属）====================
    crud_factory.register(
        model=Tenant,
        prefix="/tenants",
        tags=["tenants"],
        service_class=TenantService,
        create_schema=TenantCreate,
        update_schema=TenantUpdate,
        read_schema=TenantResponse,
        list_request_schema=TenantListRequest,
        # 租户管理需要管理员权限
        list_permissions=["admin"],
        get_permissions=["admin"],
        create_permissions=["admin"],
        update_permissions=["admin"],
        delete_permissions=["admin"]
    )
    # 完成！自动拥有纯 POST Action 风格路由：
    # - POST /list, /get, /create, /update, /delete
    
    # ==================== 用户（使用自定义路由，不使用 CRUD 工厂）====================
    # 注意：User 模型已经在 api/v1/users.py 中手动实现了完整的 CRUD 路由
    # 包括特殊的 /users/me 路由，所以不使用 CRUD 工厂自动生成
    # 
    # 如果使用 CRUD 工厂，会导致路由冲突：
    # - /users/me 会被 /users/{id} 匹配，导致尝试将 "me" 解析为 UUID
    # 
    # 已实现的路由（api/v1/users.py）：
    # - GET    /users/me       获取当前用户信息
    # - PATCH  /users/me       更新当前用户信息
    # - GET    /users          列表（需要 admin 权限，支持搜索和过滤）
    # - POST   /users          创建（需要 admin 权限，带密码强度验证）
    # - GET    /users/{id}     获取（需要 admin 权限）
    # - PUT    /users/{id}     更新（需要 admin 权限，密码可选）
    # - DELETE /users/{id}     删除（需要 admin 权限）
    pass
    
    # ==================== 知识库（带权限控制）====================
    crud_factory.register(
        model=KnowledgeBase,
        prefix="/knowledge-bases",
        tags=["knowledge-bases"],
        service_class=KnowledgeBaseService,
        create_schema=KnowledgeBaseCreate,
        update_schema=KnowledgeBaseUpdate,
        read_schema=KnowledgeBaseRead,
        # 权限控制：读写分离
        list_permissions=["kb:read", "kb:write", "admin"],
        get_permissions=["kb:read", "kb:write", "admin"],
        create_permissions=["kb:write", "admin"],
        update_permissions=["kb:write", "admin"],
        delete_permissions=["kb:delete", "admin"]
    )
    # 完成！自动拥有纯 POST Action 风格路由：
    # - POST /list, /get, /create, /update, /delete (带权限检查)
    
    # ==================== 角色管理（管理员专属）====================
    # crud_factory.register(
    #     model=Role,
    #     prefix="/roles",
    #     tags=["roles"],
    #     # 所有操作都需要管理员权限
    #     list_permissions=["admin"],
    #     get_permissions=["admin"],
    #     create_permissions=["admin"],
    #     update_permissions=["admin"],
    #     delete_permissions=["admin"]
    # )
    # 完成！自动拥有纯 POST Action 风格路由：
    # - POST /list, /get, /create, /update, /delete
    
    # ==================== 权限管理（使用自定义路由，不使用 CRUD 工厂）====================
    # 注意：Permission 模型已经在 api/v1/permissions.py 中手动实现了完整的 CRUD 路由
    # 包括特殊的权限树查询、权限分配等功能，所以不使用 CRUD 工厂自动生成
    # 
    # 已实现的路由（api/v1/permissions.py）：
    # - GET    /permissions/list    列表（支持搜索和过滤）
    # - GET    /permissions/get     获取单个权限
    # - POST   /permissions/tree    获取权限树
    # - POST   /permissions/create  创建权限
    # - POST   /permissions/update  更新权限
    # - POST   /permissions/delete  删除权限
    pass
    
    # ==================== 文档（带权限控制）====================
    # crud_factory.register(
    #     model=Document,
    #     prefix="/documents",
    #     tags=["documents"],
    #     readonly_fields=["file_hash", "file_size"],
    #     # 权限控制
    #     list_permissions=["doc:read", "doc:write", "admin"],
    #     get_permissions=["doc:read", "doc:write", "admin"],
    #     create_permissions=["doc:write", "doc:upload", "admin"],
    #     update_permissions=["doc:write", "admin"],
    #     delete_permissions=["doc:delete", "admin"]
    # )
    # ==================== 物理文档（内部管理）====================
    crud_factory.register(
        model=Document,
        prefix="/documents",
        tags=["documents"],
        service_class=DocumentService,
        read_schema=DocumentRead,
        # 物理资产通常由后台自动维护，前端只读或删除
        list_permissions=["admin"],
        get_permissions=["doc:read", "admin"],
        create_permissions=["admin"], 
        update_permissions=["admin"],
        delete_permissions=["admin"],
        # 禁用默认删除路由（使用 /documents/delete 自定义批量删除）
        enable_delete=False
    )

    # ==================== 知识库文档挂载（文件浏览器核心）====================
    crud_factory.register(
        model=KnowledgeBaseDocument,
        prefix="/kb-documents",
        tags=["kb-documents"],
        service_class=KBDocumentService,
        create_schema=KBDocumentCreate,
        update_schema=KBDocumentUpdate,
        read_schema=KBDocumentRead,
        list_request_schema=KBDocumentListRequest,
        # 权限控制
        list_permissions=["kb:read", "admin"],
        get_permissions=["kb:read", "admin"],
        create_permissions=["kb:write", "admin"],
        update_permissions=["kb:write", "admin"],
        delete_permissions=["kb:write", "admin"],
        # 禁用默认删除路由（使用 /documents/delete 自定义批量删除）
        enable_delete=False
    )
    
    # ==================== 异步任务（系统监控）====================
    crud_factory.register(
        model=Task,
        prefix="/tasks",
        tags=["tasks"],
        service_class=TaskService,
        create_schema=TaskCreate,
        update_schema=TaskUpdate,
        read_schema=TaskRead,
        list_request_schema=TaskListRequest,
        # 权限控制：用户可以看自己的任务
        list_permissions=None,
        get_permissions=None,
        # 只有系统或管理员可以创建/更新/删除任务
        create_permissions=["admin"],
        update_permissions=["admin"],
        delete_permissions=["admin"]
    )
    
    # ==================== 文本切片（只读查询）====================
    crud_factory.register(
        model=Chunk,
        prefix="/chunks",
        tags=["chunks"],
        service_class=ChunkService,  # 🔧 使用自定义 Service 处理 metadata 合并
        create_schema=ChunkCreate,
        update_schema=ChunkUpdate,
        read_schema=ChunkRead,
        list_request_schema=ChunkListRequest,
        # 权限控制：用户可以查看和编辑切片
        list_permissions=None,
        get_permissions=None,
        # 允许用户编辑切片内容、摘要和元数据（如标签）
        update_permissions=None,  # 允许登录用户编辑
        # 切片由系统自动创建和删除
        create_permissions=["admin"],
        delete_permissions=["admin"]
    )

    # ==================== 多模型平台：厂商定义（系统级）====================
    crud_factory.register(
        model=ModelProviderDefinition,
        prefix="/model-provider-definitions",
        tags=["model-platform"],
        service_class=ModelProviderDefinitionService,
        create_schema=ModelProviderDefinitionCreate,
        update_schema=ModelProviderDefinitionUpdate,
        read_schema=ModelProviderDefinitionRead,
        list_request_schema=ModelPlatformListRequest,
        list_permissions=["admin"],
        get_permissions=["admin"],
        create_permissions=["admin"],
        update_permissions=["admin"],
        delete_permissions=["admin"]
    )

    # ==================== 多模型平台：租户 Provider 实例====================
    crud_factory.register(
        model=TenantModelProvider,
        prefix="/model-providers",
        tags=["model-platform"],
        service_class=TenantModelProviderService,
        create_schema=TenantModelProviderCreate,
        update_schema=TenantModelProviderUpdate,
        read_schema=TenantModelProviderRead,
        list_request_schema=ModelPlatformListRequest,
        list_permissions=["admin"],
        get_permissions=["admin"],
        create_permissions=["admin"],
        update_permissions=["admin"],
        delete_permissions=["admin"]
    )

    # ==================== 多模型平台：Provider 凭证====================
    crud_factory.register(
        model=TenantModelProviderCredential,
        prefix="/model-provider-credentials",
        tags=["model-platform"],
        service_class=TenantModelProviderCredentialService,
        create_schema=TenantModelProviderCredentialCreate,
        update_schema=TenantModelProviderCredentialUpdate,
        read_schema=TenantModelProviderCredentialRead,
        list_request_schema=ModelPlatformListRequest,
        list_permissions=["admin"],
        get_permissions=["admin"],
        create_permissions=["admin"],
        update_permissions=["admin"],
        delete_permissions=["admin"]
    )

    # ==================== 多模型平台：平台模型目录====================
    crud_factory.register(
        model=PlatformModel,
        prefix="/platform-models",
        tags=["model-platform"],
        service_class=PlatformModelService,
        create_schema=PlatformModelCreate,
        update_schema=PlatformModelUpdate,
        read_schema=PlatformModelRead,
        list_request_schema=ModelPlatformListRequest,
        list_permissions=["admin"],
        get_permissions=["admin"],
        create_permissions=["admin"],
        update_permissions=["admin"],
        delete_permissions=["admin"]
    )

    # ==================== 多模型平台：租户模型绑定====================
    crud_factory.register(
        model=TenantModel,
        prefix="/tenant-models",
        tags=["model-platform"],
        service_class=TenantModelService,
        create_schema=TenantModelCreate,
        update_schema=TenantModelUpdate,
        read_schema=TenantModelRead,
        list_request_schema=ModelPlatformListRequest,
        list_permissions=["admin"],
        get_permissions=["admin"],
        create_permissions=["admin"],
        update_permissions=["admin"],
        delete_permissions=["admin"]
    )

    # ==================== 多模型平台：租户默认模型====================
    crud_factory.register(
        model=TenantDefaultModel,
        prefix="/tenant-default-models",
        tags=["model-platform"],
        service_class=TenantDefaultModelService,
        create_schema=TenantDefaultModelCreate,
        update_schema=TenantDefaultModelUpdate,
        read_schema=TenantDefaultModelRead,
        list_request_schema=ModelPlatformListRequest,
        list_permissions=["admin"],
        get_permissions=["admin"],
        create_permissions=["admin"],
        update_permissions=["admin"],
        delete_permissions=["admin"]
    )

    # ==================== 多模型平台：适配器绑定====================
    crud_factory.register(
        model=ModelAdapterBinding,
        prefix="/model-adapter-bindings",
        tags=["model-platform"],
        service_class=ModelAdapterBindingService,
        create_schema=ModelAdapterBindingCreate,
        update_schema=ModelAdapterBindingUpdate,
        read_schema=ModelAdapterBindingRead,
        list_request_schema=ModelPlatformListRequest,
        list_permissions=["admin"],
        get_permissions=["admin"],
        create_permissions=["admin"],
        update_permissions=["admin"],
        delete_permissions=["admin"]
    )
    
    crud_factory.register(
        model=Folder,
        prefix="/folders",
        tags=["folders"],
        service_class=FolderService,
        create_schema=FolderCreate,
        update_schema=FolderUpdate,
        read_schema=FolderRead,
        # 不指定权限，只需要登录用户即可访问
        list_permissions=None,
        get_permissions=None,
        create_permissions=None,
        update_permissions=None,
        delete_permissions=None
    )
    
    # ==================== 标签（公开读，限制写）====================
    crud_factory.register(
        model=Tag,
        prefix="/tags",
        tags=["tags"],
        service_class=TagService,  # 使用自定义 Service（带重复检查）
        create_schema=TagCreate,
        update_schema=TagUpdate,
        read_schema=TagRead,
        # 列表和获取不需要权限（只需登录）
        list_permissions=None,
        get_permissions=None,
        # 创建、修改、删除需要权限
        create_permissions=["tag:write", "admin"],
        update_permissions=["tag:write", "admin"],
        delete_permissions=["tag:delete", "admin"]
    )

    # ==================== 专业术语 ====================
    crud_factory.register(
        model=KBGlossary,
        prefix="/kb-glossaries",
        tags=["dictionary"],
        service_class=KBGlossaryService,
        create_schema=KBGlossaryCreate,
        update_schema=KBGlossaryUpdate,
        read_schema=KBGlossaryRead,
        list_permissions=["kb:read", "kb:write", "admin"],
        get_permissions=["kb:read", "kb:write", "admin"],
        create_permissions=["kb:write", "admin"],
        update_permissions=["kb:write", "admin"],
        delete_permissions=["kb:delete", "admin"]
    )

    # ==================== 同义词标准词主表 ====================
    crud_factory.register(
        model=KBSynonym,
        prefix="/kb-synonyms",
        tags=["dictionary"],
        service_class=KBSynonymService,
        create_schema=KBSynonymCreate,
        update_schema=KBSynonymUpdate,
        read_schema=KBSynonymRead,
        list_permissions=["kb:read", "kb:write", "admin"],
        get_permissions=["kb:read", "kb:write", "admin"],
        create_permissions=["kb:write", "admin"],
        update_permissions=["kb:write", "admin"],
        delete_permissions=["kb:delete", "admin"]
    )

    # ==================== 同义词口语子表 ====================
    crud_factory.register(
        model=KBSynonymVariant,
        prefix="/kb-synonym-variants",
        tags=["dictionary"],
        service_class=KBSynonymVariantService,
        create_schema=KBSynonymVariantCreate,
        update_schema=KBSynonymVariantUpdate,
        read_schema=KBSynonymVariantRead,
        list_permissions=["kb:read", "kb:write", "admin"],
        get_permissions=["kb:read", "kb:write", "admin"],
        create_permissions=["kb:write", "admin"],
        update_permissions=["kb:write", "admin"],
        delete_permissions=["kb:delete", "admin"]
    )
    
    # ==================== 审计日志（只读资源）====================
    # crud_factory.register(
    #     model=AuditLog,
    #     prefix="/audit-logs",
    #     tags=["audit-logs"],
    #     list_permissions=["audit:read", "admin"],
    #     get_permissions=["audit:read", "admin"],
    #     enable_create=False,  # 禁用创建
    #     enable_update=False,  # 禁用更新
    #     enable_delete=False   # 禁用删除
    # )
    
    # ==================== 系统配置（管理员专属）====================
    # crud_factory.register(
    #     model=SystemConfig,
    #     prefix="/system-configs",
    #     tags=["system-configs"],
    #     # 所有操作都需要管理员权限
    #     list_permissions=["admin"],
    #     get_permissions=["admin"],
    #     create_permissions=["admin"],
    #     update_permissions=["admin"],
    #     delete_permissions=["admin"]
    # )
    
    # ==================== 权限说明 ====================
    # 
    # 权限配置参数：
    # - list_permissions: 列表操作所需权限
    # - get_permissions: 获取单个资源所需权限
    # - create_permissions: 创建操作所需权限
    # - update_permissions: 更新操作所需权限
    # - delete_permissions: 删除操作所需权限
    #
    # 权限逻辑：
    # - 如果不指定（None）：只需要登录用户
    # - 如果指定列表：用户需要拥有列表中任意一个权限（OR 逻辑）
    # - 示例：["kb:read", "admin"] 表示拥有 kb:read 或 admin 权限即可
    #
    # 详细说明请查看：权限控制使用指南.md
    
    pass


def get_all_crud_routers():
    """获取所有已注册的 CRUD 路由"""
    return crud_factory.get_all_routers()
