"""
文件夹标签服务
"""
from typing import List
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from models.folder import Folder
from models.tag import Tag
from models.resource_tag import ResourceTag, TARGET_TYPE_FOLDER
from schemas.tag import TagRead


class FolderTagService:
    """文件夹标签服务"""

    @staticmethod
    async def _validate_tags(
        session: AsyncSession,
        tag_ids: List[UUID],
        tenant_id: UUID,
        kb_id: UUID | None,
    ) -> None:
        """校验标签是否允许绑定到文件夹。"""
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
            if TARGET_TYPE_FOLDER not in (tag.allowed_target_types or ["kb_doc"]):
                invalid_tag_ids.append(str(tag_id))

        if invalid_tag_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"存在不适用于文件夹标签的标签: {', '.join(invalid_tag_ids)}",
            )
    
    @staticmethod
    async def get_folder_tags(
        session: AsyncSession,
        folder_id: UUID,
        tenant_id: UUID
    ) -> List[TagRead]:
        """
        获取文件夹的所有标签
        
        Args:
            session: 数据库会话
            folder_id: 文件夹ID
            tenant_id: 租户ID
            
        Returns:
            标签列表
        """
        # 查询文件夹的标签关联
        stmt = (
            select(Tag)
            .join(ResourceTag, ResourceTag.tag_id == Tag.id)
            .where(
                ResourceTag.tenant_id == tenant_id,
                ResourceTag.target_id == folder_id,
                ResourceTag.target_type == TARGET_TYPE_FOLDER,
                ResourceTag.action == "add"
            )
        )
        
        result = await session.execute(stmt)
        tags = result.scalars().all()
        
        return [TagRead.model_validate(tag) for tag in tags]
    
    @staticmethod
    async def set_folder_tags(
        session: AsyncSession,
        folder_id: UUID,
        tag_ids: List[UUID],
        tenant_id: UUID,
        kb_id: UUID | None = None
    ) -> List[TagRead]:
        """
        设置文件夹的标签（替换现有标签）
        
        Args:
            session: 数据库会话
            folder_id: 文件夹ID
            tag_ids: 标签ID列表
            tenant_id: 租户ID
            kb_id: 知识库ID
            
        Returns:
            更新后的标签列表
        """
        await FolderTagService._validate_tags(session, tag_ids, tenant_id, kb_id)

        # 1. 删除现有的标签关联
        delete_stmt = delete(ResourceTag).where(
            ResourceTag.tenant_id == tenant_id,
            ResourceTag.target_id == folder_id,
            ResourceTag.target_type == TARGET_TYPE_FOLDER
        )
        await session.execute(delete_stmt)
        
        # 2. 添加新的标签关联
        for tag_id in tag_ids:
            resource_tag = ResourceTag(
                tenant_id=tenant_id,
                tag_id=tag_id,
                target_id=folder_id,
                target_type=TARGET_TYPE_FOLDER,
                kb_id=kb_id,
                action="add"
            )
            session.add(resource_tag)
        
        await session.commit()
        
        # 3. 返回更新后的标签列表
        return await FolderTagService.get_folder_tags(session, folder_id, tenant_id)
    
    @staticmethod
    async def add_folder_tag(
        session: AsyncSession,
        folder_id: UUID,
        tag_id: UUID,
        tenant_id: UUID,
        kb_id: UUID | None = None
    ) -> TagRead:
        """
        为文件夹添加单个标签
        
        Args:
            session: 数据库会话
            folder_id: 文件夹ID
            tag_id: 标签ID
            tenant_id: 租户ID
            kb_id: 知识库ID
            
        Returns:
            添加的标签
        """
        await FolderTagService._validate_tags(session, [tag_id], tenant_id, kb_id)

        # 检查是否已存在
        stmt = select(ResourceTag).where(
            ResourceTag.tenant_id == tenant_id,
            ResourceTag.target_id == folder_id,
            ResourceTag.target_type == TARGET_TYPE_FOLDER,
            ResourceTag.tag_id == tag_id,
            ResourceTag.action == "add"
        )
        existing = await session.scalar(stmt)
        
        if not existing:
            # 添加新的标签关联
            resource_tag = ResourceTag(
                tenant_id=tenant_id,
                tag_id=tag_id,
                target_id=folder_id,
                target_type=TARGET_TYPE_FOLDER,
                kb_id=kb_id,
                action="add"
            )
            session.add(resource_tag)
            await session.commit()
        
        # 返回标签信息
        tag = await session.get(Tag, tag_id)
        return TagRead.model_validate(tag)
    
    @staticmethod
    async def remove_folder_tag(
        session: AsyncSession,
        folder_id: UUID,
        tag_id: UUID,
        tenant_id: UUID
    ) -> None:
        """
        移除文件夹的标签
        
        Args:
            session: 数据库会话
            folder_id: 文件夹ID
            tag_id: 标签ID
            tenant_id: 租户ID
        """
        delete_stmt = delete(ResourceTag).where(
            ResourceTag.tenant_id == tenant_id,
            ResourceTag.target_id == folder_id,
            ResourceTag.target_type == TARGET_TYPE_FOLDER,
            ResourceTag.tag_id == tag_id
        )
        await session.execute(delete_stmt)
        await session.commit()
