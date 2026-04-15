"""
标签 API 路由（扩展 CRUD 工厂生成的路由）

CRUD 工厂已自动生成以下路由：
- POST /tags/list    - 列表查询（支持分页、搜索、过滤）
- POST /tags/get     - 获取单个标签
- POST /tags/create  - 创建标签
- POST /tags/update  - 更新标签
- POST /tags/delete  - 删除标签

本文件添加额外的自定义路由：
- GET /tags/check-duplicate - 检查标签名是否重复
- POST /tags/get-available-tags - 获取可选标签（按资源类型过滤）
- POST /tags/list-scoped - 获取当前知识库可用标签池（公共 + 本库）
"""
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, and_, distinct, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_async_session
from core.security.auth import get_current_user
from models.user import User
from models.tag import Tag
from models.resource_tag import ResourceTag
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.folder import Folder
from models.document import Document
from models.resource_tag import TARGET_TYPE_FOLDER, TARGET_TYPE_KB, TARGET_TYPE_KB_DOC
from schemas.tag import TagRead

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("/check-duplicate")
async def check_tag_duplicate(
    kb_id: str = Query(..., description="知识库ID"),
    name: str = Query(..., description="标签名称"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    检查标签名是否重复
    
    用于前端实时校验，避免创建重复标签
    
    查询参数：
    - kb_id: 知识库ID
    - name: 标签名称
    
    返回：
    - exists: 是否存在
    - tag: 如果存在，返回标签详情
    """
    # 转换 UUID
    kb_uuid = UUID(kb_id)
    
    # 查询标签（同一知识库内）
    stmt = select(Tag).where(
        and_(
            Tag.tenant_id == current_user.tenant_id,
            Tag.kb_id == kb_uuid,
            Tag.name == name.strip()
        )
    )
    result = await session.execute(stmt)
    existing_tag = result.scalar_one_or_none()
    
    if existing_tag:
        return {
            "exists": True,
            "tag": TagRead.model_validate(existing_tag)
        }
    else:
        return {
            "exists": False,
            "tag": None
        }


class GetAvailableTagsRequest(BaseModel):
    """获取可选标签请求"""
    kb_id: str
    target_type: str  # 'folder' / 'kb' / 'kb_doc'
    search: Optional[str] = None
    limit: Optional[int] = 100


class ScopedTagsRequest(BaseModel):
    """
    按作用域获取标签池请求。

    筛选字段说明：
    - scope: 标签来源筛选，'all'=全部 / 'global'=公共标签 / 'kb'=本库私有标签
    - target_types: 适用对象多选筛选，传入 ['kb', 'kb_doc', 'folder'] 的子集
    - association_status: 关联状态，'all'=全部 / 'bound'=已关联 / 'unbound'=未关联
    - usage_status: 使用状态，'all'=全部 / 'used'=已使用 / 'unused'=未使用
    - page / page_size: 服务端真分页
    """
    kb_id: Optional[str] = None
    # 兼容旧字段，由 scope 替代
    include_global: bool = True
    include_kb: bool = True
    # 新增：标签来源筛选
    scope: Optional[str] = None  # 'all' | 'global' | 'kb'
    # 新增：适用对象多选（替代单一 target_type）
    target_types: Optional[List[str]] = None  # e.g. ['kb', 'kb_doc']
    target_type: Optional[str] = None  # 保留单选兼容
    # 新增：关联状态筛选（标签是否已关联到当前 kb 实体）
    association_status: Optional[str] = None  # 'all' | 'bound' | 'unbound'
    # 新增：使用状态筛选（标签是否被挂载到任意资源对象）
    usage_status: Optional[str] = None  # 'all' | 'used' | 'unused'
    search: Optional[str] = None
    # 旧字段 limit 保留兼容；新接口以 page/page_size 为准
    limit: Optional[int] = None
    page: Optional[int] = 1
    page_size: Optional[int] = 24


class TagUsageSummaryRequest(BaseModel):
    """标签使用概览请求。"""
    tag_ids: List[str]
    kb_id: Optional[str] = None
    sample_limit: int = 3


class TagUsageDetailRequest(BaseModel):
    """标签使用明细请求。"""
    tag_id: str
    kb_id: Optional[str] = None
    limit: int = 100


@router.post("/get-available-tags")
async def get_available_tags(
    request: GetAvailableTagsRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    获取可选标签列表（按资源类型过滤）
    
    根据 target_type 查询 resource_tags 表中已使用的标签，
    这样可以为用户提供精确的可选标签列表。
    
    请求体：
    - kb_id: 知识库ID
    - target_type: 资源类型 ('folder' / 'kb' / 'kb_doc')
    - search: 可选，标签名称搜索
    - limit: 可选，返回数量限制（默认100）
    
    返回：
    - tags: 标签列表
    - total: 总数量
    """
    # 转换 UUID
    kb_uuid = UUID(request.kb_id)
    
    # 验证 target_type
    if request.target_type not in ['folder', 'kb', 'kb_doc']:
        raise HTTPException(
            status_code=400,
            detail="target_type must be 'folder', 'kb' or 'kb_doc'"
        )
    
    # 改为基于标签定义的适用对象 + 作用域过滤，而不是“历史上是否用过”。
    # 这样新创建但尚未绑定的标签也能被正确选到，符合快速建标签的使用习惯。
    stmt = (
        select(Tag)
        .where(
            and_(
                Tag.tenant_id == current_user.tenant_id,
                Tag.allowed_target_types.contains([request.target_type]),
                or_(
                    Tag.kb_id.is_(None),
                    Tag.kb_id == kb_uuid,
                ),
            )
        )
    )
    
    # 添加搜索条件
    if request.search:
        search_term = f"%{request.search.strip()}%"
        stmt = stmt.where(Tag.name.ilike(search_term))
    
    # 排序和限制
    stmt = stmt.order_by(Tag.name).limit(request.limit or 100)
    
    # 执行查询
    result = await session.execute(stmt)
    tags = result.scalars().all()
    
    # 构建响应
    tags_list = []
    for tag in tags:
        tags_list.append({
            "id": str(tag.id),
            "name": tag.name,
            "color": tag.color,
            "description": tag.description,
            "aliases": tag.aliases or [],
            "allowed_target_types": tag.allowed_target_types or ["kb_doc"],
            "kb_id": str(tag.kb_id) if tag.kb_id else None,
        })
    
    return {
        "success": True,
        "message": f"获取 {request.target_type} 可选标签成功",
        "data": {
            "tags": tags_list,
            "total": len(tags_list),
            "kb_id": request.kb_id,
            "target_type": request.target_type
        }
    }


@router.post("/list-scoped")
async def list_scoped_tags(
    request: ScopedTagsRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前作用域下可用标签池，支持服务端多维筛选 + 真分页。

    筛选规则：
    - scope / include_global / include_kb 决定标签来源范围
    - target_types / target_type 按适用对象过滤
    - association_status 按关联到当前 kb 的状态过滤
    - usage_status 按标签是否被任意资源使用过滤
    - search 模糊匹配名称和描述
    - page / page_size 服务端分页
    """
    normalized_kb_id = UUID(request.kb_id) if request.kb_id else None
    conditions = [Tag.tenant_id == current_user.tenant_id]

    # ── 1. 标签来源（scope）────────────────────────────────────────────────
    # scope 优先；如果未传 scope，则退回到旧字段 include_global/include_kb
    scope = request.scope or "all"
    if scope == "global":
        conditions.append(Tag.kb_id.is_(None))
    elif scope == "kb" and normalized_kb_id is not None:
        conditions.append(Tag.kb_id == normalized_kb_id)
    else:
        # all：按旧字段决定公共 + 本库的并集
        scope_conditions: list = []
        if request.include_global:
            scope_conditions.append(Tag.kb_id.is_(None))
        if request.include_kb and normalized_kb_id is not None:
            scope_conditions.append(Tag.kb_id == normalized_kb_id)
        if not scope_conditions:
            return {
                "success": True,
                "message": "获取作用域标签成功",
                "data": {"tags": [], "total": 0},
            }
        conditions.append(or_(*scope_conditions))

    # ── 2. 适用对象（target_types 多选，兼容旧 target_type 单选）──────────
    effective_target_types = request.target_types or (
        [request.target_type] if request.target_type else None
    )
    if effective_target_types:
        # 标签的 allowed_target_types 包含任意一个所选类型即满足条件
        type_conditions = [
            Tag.allowed_target_types.contains([t]) for t in effective_target_types
        ]
        conditions.append(or_(*type_conditions))

    # ── 3. 关键词搜索（名称 + 描述）───────────────────────────────────────
    if request.search:
        search_term = f"%{request.search.strip()}%"
        conditions.append(
            or_(
                Tag.name.ilike(search_term),
                Tag.description.ilike(search_term),
            )
        )

    # ── 4. 关联状态（association_status）─────────────────────────────────
    # 关联状态：标签是否通过 resource_tags(target_type=kb) 关联到当前知识库实体
    association_status = request.association_status or "all"
    if association_status in ("bound", "unbound") and normalized_kb_id is not None:
        bound_subq = (
            select(ResourceTag.tag_id)
            .where(
                and_(
                    ResourceTag.tenant_id == current_user.tenant_id,
                    ResourceTag.target_id == normalized_kb_id,
                    ResourceTag.target_type == TARGET_TYPE_KB,
                    ResourceTag.action == "add",
                )
            )
            .scalar_subquery()
        )
        if association_status == "bound":
            conditions.append(Tag.id.in_(bound_subq))
        else:  # unbound
            conditions.append(Tag.id.not_in(bound_subq))

    # ── 5. 使用状态（usage_status）────────────────────────────────────────
    # 使用状态：标签是否被挂载到任意资源（知识库/文档/文件夹）
    usage_status = request.usage_status or "all"
    if usage_status in ("used", "unused"):
        used_subq = (
            select(ResourceTag.tag_id)
            .where(
                and_(
                    ResourceTag.tenant_id == current_user.tenant_id,
                    ResourceTag.action == "add",
                )
            )
            .scalar_subquery()
        )
        if usage_status == "used":
            conditions.append(Tag.id.in_(used_subq))
        else:  # unused
            conditions.append(Tag.id.not_in(used_subq))

    # ── 6. 分页计算 ───────────────────────────────────────────────────────
    page = max(1, request.page or 1)
    page_size = max(1, min(request.page_size or 24, 100))
    offset = (page - 1) * page_size

    base_where = and_(*conditions)

    # 查询总数
    count_stmt = select(func.count()).select_from(Tag).where(base_where)
    total: int = int((await session.execute(count_stmt)).scalar() or 0)

    # 查询分页数据
    stmt = (
        select(Tag)
        .where(base_where)
        .order_by(Tag.kb_id.is_not(None).asc(), Tag.name.asc())
        .offset(offset)
        .limit(page_size)
    )
    tags = (await session.execute(stmt)).scalars().all()

    tags_list = [
        {
            "id": str(tag.id),
            "tenant_id": str(tag.tenant_id),
            "name": tag.name,
            "color": tag.color,
            "description": tag.description,
            "aliases": tag.aliases or [],
            "allowed_target_types": tag.allowed_target_types or ["kb_doc"],
            "kb_id": str(tag.kb_id) if tag.kb_id else None,
            "created_by_id": str(tag.created_by_id) if tag.created_by_id else None,
            "created_by_name": tag.created_by_name,
            "updated_by_id": str(tag.updated_by_id) if tag.updated_by_id else None,
            "updated_by_name": tag.updated_by_name,
            "created_at": tag.created_at.isoformat() if tag.created_at else None,
            "updated_at": tag.updated_at.isoformat() if tag.updated_at else None,
        }
        for tag in tags
    ]

    return {
        "success": True,
        "message": "获取作用域标签成功",
        "data": {
            "tags": tags_list,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.post("/usage-summary")
async def get_tag_usage_summary(
    request: TagUsageSummaryRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """
    获取标签使用概览。

    用于标签管理页展示：
    - 被多少个知识库使用
    - 被多少个知识库文档使用
    - 当前知识库下有哪些文档正在使用
    - 哪些知识库正在使用该标签（示例）
    """
    if not request.tag_ids:
        return {
            "success": True,
            "message": "获取标签使用概览成功",
            "data": {"items": []},
        }

    try:
        tag_ids = [UUID(tag_id) for tag_id in request.tag_ids]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="tag_ids 包含非法 UUID") from exc

    normalized_kb_id = UUID(request.kb_id) if request.kb_id else None
    sample_limit = max(1, min(request.sample_limit or 3, 10))

    # 仅允许查询当前租户内的标签，避免越权读取其它租户的使用情况。
    tag_stmt = select(Tag).where(
        and_(
            Tag.tenant_id == current_user.tenant_id,
            Tag.id.in_(tag_ids),
        )
    )
    tag_rows = (await session.execute(tag_stmt)).scalars().all()
    tag_map = {tag.id: tag for tag in tag_rows}

    items = []
    for tag_id in tag_ids:
        tag = tag_map.get(tag_id)
        if tag is None:
            continue

        kb_count_stmt = select(func.count(distinct(ResourceTag.target_id))).where(
            and_(
                ResourceTag.tenant_id == current_user.tenant_id,
                ResourceTag.tag_id == tag_id,
                ResourceTag.target_type == TARGET_TYPE_KB,
                ResourceTag.action == "add",
            )
        )
        kb_doc_count_stmt = select(func.count(distinct(ResourceTag.target_id))).where(
            and_(
                ResourceTag.tenant_id == current_user.tenant_id,
                ResourceTag.tag_id == tag_id,
                ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                ResourceTag.action == "add",
            )
        )
        folder_count_stmt = select(func.count(distinct(ResourceTag.target_id))).where(
            and_(
                ResourceTag.tenant_id == current_user.tenant_id,
                ResourceTag.tag_id == tag_id,
                ResourceTag.target_type == TARGET_TYPE_FOLDER,
                ResourceTag.action == "add",
            )
        )

        kb_count = int((await session.execute(kb_count_stmt)).scalar() or 0)
        kb_doc_count = int((await session.execute(kb_doc_count_stmt)).scalar() or 0)
        folder_count = int((await session.execute(folder_count_stmt)).scalar() or 0)

        kb_name_stmt = (
            select(KnowledgeBase.id, KnowledgeBase.name)
            .join(
                ResourceTag,
                and_(
                    ResourceTag.target_id == KnowledgeBase.id,
                    ResourceTag.target_type == TARGET_TYPE_KB,
                    ResourceTag.tag_id == tag_id,
                    ResourceTag.action == "add",
                ),
            )
            .where(KnowledgeBase.tenant_id == current_user.tenant_id)
            .order_by(KnowledgeBase.name.asc())
            .limit(sample_limit)
        )
        kb_name_rows = (await session.execute(kb_name_stmt)).all()
        kb_samples = [
            {"id": str(kb_row.id), "name": kb_row.name}
            for kb_row in kb_name_rows
        ]

        folder_name_stmt = (
            select(Folder.id, Folder.name)
            .join(
                ResourceTag,
                and_(
                    ResourceTag.target_id == Folder.id,
                    ResourceTag.target_type == TARGET_TYPE_FOLDER,
                    ResourceTag.tag_id == tag_id,
                    ResourceTag.action == "add",
                ),
            )
            .where(Folder.tenant_id == current_user.tenant_id)
            .order_by(Folder.name.asc())
            .limit(sample_limit)
        )
        folder_name_rows = (await session.execute(folder_name_stmt)).all()
        folder_samples = [
            {"id": str(folder_row.id), "name": folder_row.name}
            for folder_row in folder_name_rows
        ]

        current_kb_doc_count = 0
        current_kb_doc_samples: list[dict] = []
        if normalized_kb_id is not None:
            current_kb_doc_count_stmt = select(func.count(distinct(KnowledgeBaseDocument.id))).join(
                ResourceTag,
                and_(
                    ResourceTag.target_id == KnowledgeBaseDocument.id,
                    ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                    ResourceTag.tag_id == tag_id,
                    ResourceTag.action == "add",
                ),
            ).where(
                and_(
                    KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
                    KnowledgeBaseDocument.kb_id == normalized_kb_id,
                )
            )
            current_kb_doc_count = int((await session.execute(current_kb_doc_count_stmt)).scalar() or 0)

            current_kb_doc_stmt = (
                select(
                    KnowledgeBaseDocument.id,
                    KnowledgeBaseDocument.display_name,
                    Document.name,
                )
                .join(
                    ResourceTag,
                    and_(
                        ResourceTag.target_id == KnowledgeBaseDocument.id,
                        ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                        ResourceTag.tag_id == tag_id,
                        ResourceTag.action == "add",
                    ),
                )
                .join(
                    Document,
                    Document.id == KnowledgeBaseDocument.document_id,
                    isouter=True,
                )
                .where(
                    and_(
                        KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
                        KnowledgeBaseDocument.kb_id == normalized_kb_id,
                    )
                )
                .order_by(KnowledgeBaseDocument.updated_at.desc())
                .limit(sample_limit)
            )
            current_kb_doc_rows = (await session.execute(current_kb_doc_stmt)).all()
            current_kb_doc_samples = [
                {
                    "id": str(doc_row.id),
                    "name": doc_row.display_name or doc_row.name or "未命名文档",
                }
                for doc_row in current_kb_doc_rows
            ]

        items.append(
            {
                "tag_id": str(tag.id),
                "tag_name": tag.name,
                "kb_count": kb_count,
                "kb_doc_count": kb_doc_count,
                "folder_count": folder_count,
                "kb_samples": kb_samples,
                "folder_samples": folder_samples,
                "current_kb_doc_count": current_kb_doc_count,
                "current_kb_doc_samples": current_kb_doc_samples,
            }
        )

    return {
        "success": True,
        "message": "获取标签使用概览成功",
        "data": {
            "items": items,
        },
    }


@router.post("/usage-detail")
async def get_tag_usage_detail(
    request: TagUsageDetailRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """
    获取单个标签的使用明细。

    主要给前端弹窗使用，返回：
    - 正在使用该标签的知识库列表
    - 正在使用该标签的文档列表（附带所属知识库名称）
    """
    try:
        tag_id = UUID(request.tag_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="tag_id 非法") from exc

    normalized_kb_id = UUID(request.kb_id) if request.kb_id else None
    limit = max(1, min(request.limit or 100, 300))

    tag_stmt = select(Tag).where(
        and_(
            Tag.id == tag_id,
            Tag.tenant_id == current_user.tenant_id,
        )
    )
    tag = (await session.execute(tag_stmt)).scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")

    kb_stmt = (
        select(KnowledgeBase.id, KnowledgeBase.name)
        .join(
            ResourceTag,
            and_(
                ResourceTag.target_id == KnowledgeBase.id,
                ResourceTag.target_type == TARGET_TYPE_KB,
                ResourceTag.tag_id == tag_id,
                ResourceTag.action == "add",
            ),
        )
        .where(KnowledgeBase.tenant_id == current_user.tenant_id)
        .order_by(KnowledgeBase.name.asc())
        .limit(limit)
    )
    kb_rows = (await session.execute(kb_stmt)).all()
    kb_usages = [
        {"id": str(row.id), "name": row.name}
        for row in kb_rows
    ]

    folder_stmt = (
        select(Folder.id, Folder.name)
        .join(
            ResourceTag,
            and_(
                ResourceTag.target_id == Folder.id,
                ResourceTag.target_type == TARGET_TYPE_FOLDER,
                ResourceTag.tag_id == tag_id,
                ResourceTag.action == "add",
            ),
        )
        .where(Folder.tenant_id == current_user.tenant_id)
        .order_by(Folder.name.asc())
        .limit(limit)
    )
    folder_rows = (await session.execute(folder_stmt)).all()
    folder_usages = [
        {"id": str(row.id), "name": row.name}
        for row in folder_rows
    ]

    kb_doc_stmt = (
        select(
            KnowledgeBaseDocument.id,
            KnowledgeBaseDocument.display_name,
            Document.name.label("document_name"),
            KnowledgeBase.id.label("kb_id"),
            KnowledgeBase.name.label("kb_name"),
        )
        .join(
            ResourceTag,
            and_(
                ResourceTag.target_id == KnowledgeBaseDocument.id,
                ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                ResourceTag.tag_id == tag_id,
                ResourceTag.action == "add",
            ),
        )
        .join(
            KnowledgeBase,
            and_(
                KnowledgeBase.id == KnowledgeBaseDocument.kb_id,
                KnowledgeBase.tenant_id == current_user.tenant_id,
            ),
        )
        .join(Document, Document.id == KnowledgeBaseDocument.document_id, isouter=True)
        .where(KnowledgeBaseDocument.tenant_id == current_user.tenant_id)
    )
    if normalized_kb_id is not None:
        kb_doc_stmt = kb_doc_stmt.where(KnowledgeBaseDocument.kb_id == normalized_kb_id)

    kb_doc_stmt = kb_doc_stmt.order_by(
        KnowledgeBase.name.asc(),
        KnowledgeBaseDocument.updated_at.desc(),
    ).limit(limit)

    kb_doc_rows = (await session.execute(kb_doc_stmt)).all()
    kb_doc_usages = [
        {
            "id": str(row.id),
            "name": row.display_name or row.document_name or "未命名文档",
            "kb_id": str(row.kb_id),
            "kb_name": row.kb_name,
        }
        for row in kb_doc_rows
    ]

    return {
        "success": True,
        "message": "获取标签使用明细成功",
        "data": {
            "tag_id": str(tag.id),
            "tag_name": tag.name,
            "kb_usages": kb_usages,
            "folder_usages": folder_usages,
            "kb_doc_usages": kb_doc_usages,
        },
    }
