"""
API v1 路由汇总
"""
from fastapi import APIRouter
from api.v1 import (
    users,
    auth,
    health,
    captcha,
    password,
    profile,
    permissions,
    roles,
    organizations,
    documents,
    qa_items,
    table_rows,
    web_sync,
    model_platform,
    dictionary,
    chat,
)
from api.crud_registry import register_all_crud, get_all_crud_routers

# 创建 v1 路由
api_router = APIRouter()

# ==================== 注册标准 CRUD 路由 ====================
# 自动注册所有在 crud_registry.py 中配置的 CRUD 路由
register_all_crud()

# 导入自定义路由（必须在 register_all_crud 之后）
from api.v1 import chunks, folders, folder_tags, tags, knowledge_bases, kb_doc_tags, kb_tags, dictionary  # noqa: E402

for router in get_all_crud_routers():
    api_router.include_router(router)

# ==================== 注册自定义路由 ====================
# 需要特殊处理的路由手动注册
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(captcha.router, prefix="/captcha", tags=["captcha"])
api_router.include_router(password.router, prefix="/password", tags=["password"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(profile.router)  # profile 路由已包含 prefix
api_router.include_router(users.router)  # users 路由已包含 prefix
api_router.include_router(permissions.router)  # permissions 路由已包含 prefix
api_router.include_router(roles.router)  # roles 路由已包含 prefix
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(folder_tags.router)  # 文件夹标签路由
api_router.include_router(kb_tags.router)  # 知识库标签路由（resource_tags.target_type=kb）
api_router.include_router(kb_doc_tags.router)  # 知识库文档标签路由（resource_tags.target_type=kb_doc）
api_router.include_router(tags.router)  # 标签扩展路由（check-duplicate）
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])  # 文档上传路由
api_router.include_router(qa_items.router)  # QA 数据集与内容项路由
api_router.include_router(table_rows.router)  # 表格数据集与行维护路由
api_router.include_router(web_sync.router)  # 网页同步路由
api_router.include_router(model_platform.router)  # 多模型平台动作路由
api_router.include_router(dictionary.router)  # 词典扩展路由（改写预览）
api_router.include_router(chat.router)  # 聊天模块路由

# 如果某个资源需要额外的自定义路由，可以这样：
# from . import knowledge_bases_custom
# api_router.include_router(knowledge_bases_custom.router)
# 注意：以下路由已通过 CRUD 工厂自动注册，并在各自的文件中添加了自定义路由
# - knowledge_bases.router: 知识库 CRUD + 文档管理（/attach, /list, /detach）
# - folders.router: 文件夹 CRUD + 树形结构（/tree）
# - tags.router: 标签 CRUD，tags.router 提供额外的自定义路由（/check-duplicate）
