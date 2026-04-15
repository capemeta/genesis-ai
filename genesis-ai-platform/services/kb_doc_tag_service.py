"""
知识库文档标签服务

resource_tags：target_type=kb_doc，target_id=knowledge_base_documents.id
"""
from typing import List
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from models.tag import Tag
from models.resource_tag import ResourceTag, TARGET_TYPE_KB_DOC
from models.knowledge_base_document import KnowledgeBaseDocument
from schemas.tag import TagRead


class KbDocTagService:
    """知识库文档标签服务（resource_tags.target_type=kb_doc）"""

    @staticmethod
    async def _validate_tags(
        session: AsyncSession,
        tag_ids: List[UUID],
        tenant_id: UUID,
        kb_id: UUID | None,
    ) -> None:
        """校验标签是否允许绑定到知识库文档。"""
        if not tag_ids:
            return

        stmt = select(Tag).where(
            Tag.tenant_id == tenant_id,
            Tag.id.in_(tag_ids),
        )
        tags = (await session.execute(stmt)).scalars().all()
        tag_map = {tag.id: tag for tag in tags}
        invalid_tag_ids: list[str] = []
        for tag_id in tag_ids:
            tag = tag_map.get(tag_id)
            if tag is None:
                invalid_tag_ids.append(str(tag_id))
                continue
            if tag.kb_id is not None and tag.kb_id != kb_id:
                invalid_tag_ids.append(str(tag_id))
                continue
            if TARGET_TYPE_KB_DOC not in (tag.allowed_target_types or ["kb_doc"]):
                invalid_tag_ids.append(str(tag_id))

        if invalid_tag_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"存在不适用于文档标签的标签: {', '.join(invalid_tag_ids)}",
            )

    @staticmethod
    async def get_kb_doc_tags(
        session: AsyncSession,
        kb_doc_id: UUID,
        tenant_id: UUID,
    ) -> List[TagRead]:
        """
        获取知识库文档的所有标签

        Args:
            session: 数据库会话
            kb_doc_id: 知识库文档 ID（knowledge_base_documents.id）
            tenant_id: 租户ID

        Returns:
            标签列表
        """
        stmt = (
            select(Tag)
            .join(ResourceTag, ResourceTag.tag_id == Tag.id)
            .where(
                ResourceTag.tenant_id == tenant_id,
                ResourceTag.target_id == kb_doc_id,
                ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                ResourceTag.action == "add",
            )
        )
        result = await session.execute(stmt)
        tags = result.scalars().all()
        return [TagRead.model_validate(tag) for tag in tags]

    @staticmethod
    async def set_kb_doc_tags(
        session: AsyncSession,
        kb_doc_id: UUID,
        tag_ids: List[UUID],
        tenant_id: UUID,
        kb_id: UUID | None = None,
    ) -> List[TagRead]:
        """
        设置知识库文档的标签（替换现有标签）

        Args:
            session: 数据库会话
            kb_doc_id: 知识库文档 ID（knowledge_base_documents.id）
            tag_ids: 标签ID列表
            tenant_id: 租户ID
            kb_id: 知识库ID

        Returns:
            更新后的标签列表
        """
        await KbDocTagService._validate_tags(session, tag_ids, tenant_id, kb_id)

        delete_stmt = delete(ResourceTag).where(
            ResourceTag.tenant_id == tenant_id,
            ResourceTag.target_id == kb_doc_id,
            ResourceTag.target_type == TARGET_TYPE_KB_DOC,
        )
        await session.execute(delete_stmt)

        for tag_id in tag_ids:
            resource_tag = ResourceTag(
                tenant_id=tenant_id,
                tag_id=tag_id,
                target_id=kb_doc_id,
                target_type=TARGET_TYPE_KB_DOC,
                kb_id=kb_id,
                action="add",
            )
            session.add(resource_tag)

        await session.commit()
        return await KbDocTagService.get_kb_doc_tags(session, kb_doc_id, tenant_id)
