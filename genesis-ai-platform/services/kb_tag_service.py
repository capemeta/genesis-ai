"""
知识库标签服务

resource_tags：target_type=kb，target_id=knowledge_bases.id
"""
from typing import List
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.resource_tag import ResourceTag, TARGET_TYPE_KB
from models.tag import Tag
from schemas.tag import TagRead


class KbTagService:
    """知识库标签服务（resource_tags.target_type=kb）。"""

    @staticmethod
    async def get_kb_tags(
        session: AsyncSession,
        kb_id: UUID,
        tenant_id: UUID,
    ) -> List[TagRead]:
        """获取知识库的所有标签。"""
        stmt = (
            select(Tag)
            .join(ResourceTag, ResourceTag.tag_id == Tag.id)
            .where(
                ResourceTag.tenant_id == tenant_id,
                ResourceTag.target_id == kb_id,
                ResourceTag.target_type == TARGET_TYPE_KB,
                ResourceTag.action == "add",
            )
            .order_by(Tag.name.asc())
        )
        result = await session.execute(stmt)
        return [TagRead.model_validate(tag) for tag in result.scalars().all()]

    @staticmethod
    async def set_kb_tags(
        session: AsyncSession,
        kb_id: UUID,
        tag_ids: List[UUID],
        tenant_id: UUID,
    ) -> List[TagRead]:
        """设置知识库标签（全量替换）。"""
        await session.execute(
            delete(ResourceTag).where(
                ResourceTag.tenant_id == tenant_id,
                ResourceTag.target_id == kb_id,
                ResourceTag.target_type == TARGET_TYPE_KB,
            )
        )

        for tag_id in tag_ids:
            session.add(
                ResourceTag(
                    tenant_id=tenant_id,
                    tag_id=tag_id,
                    target_id=kb_id,
                    target_type=TARGET_TYPE_KB,
                    kb_id=kb_id,
                    action="add",
                )
            )

        await session.commit()
        return await KbTagService.get_kb_tags(session, kb_id, tenant_id)
