"""
标签服务

提供标签的业务逻辑，包括重复检查、创建、更新等
"""
from typing import Any, Dict, Optional, List
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select, and_, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_service import BaseService
from models.tag import Tag
from models.resource_tag import ResourceTag, TARGET_TYPE_FOLDER, TARGET_TYPE_KB, TARGET_TYPE_KB_DOC
from models.user import User
from schemas.tag import TagCreate, TagUpdate

ALLOWED_TAG_TARGET_TYPES = {"folder", "kb", "kb_doc"}


class TagService(BaseService[Tag, TagCreate, TagUpdate]):
    """
    标签服务
    
    扩展 BaseService，添加标签特有的业务逻辑：
    - 知识库级别的重复检查
    - 标签名称规范化
    - 标签适用对象校验
    """

    @staticmethod
    def _normalize_allowed_target_types(raw_value: Any) -> list[str]:
        """规范化标签适用对象，确保协议稳定。"""
        values = raw_value if isinstance(raw_value, list) else ["kb_doc"]
        normalized: list[str] = []
        for value in values:
            value_str = str(value).strip()
            if not value_str:
                continue
            if value_str not in ALLOWED_TAG_TARGET_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"不支持的标签适用对象：{value_str}"
                )
            if value_str not in normalized:
                normalized.append(value_str)

        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="标签至少需要一个适用对象"
            )
        return normalized
    
    async def create(
        self,
        data: TagCreate | Dict[str, Any],
        current_user: User,
        session: Optional[AsyncSession] = None
    ) -> Tag:
        """
        创建标签（带重复检查）
        
        Args:
            data: 标签创建数据
            current_user: 当前用户
            session: 数据库会话
            
        Returns:
            创建的标签对象
            
        Raises:
            HTTPException: 如果标签名重复
        """
        # 转换为字典（如果是 Pydantic 模型）
        if hasattr(data, 'model_dump'):
            data_dict = data.model_dump(exclude_unset=True)
        else:
            data_dict = dict(data)
        
        use_session = session or self.db
        
        # 规范化标签名称
        tag_name = data_dict.get('name', '').strip()
        if not tag_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="标签名称不能为空"
            )
        
        if len(tag_name) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="标签名称不能超过 100 个字符"
            )
        
        data_dict['name'] = tag_name
        data_dict['allowed_target_types'] = self._normalize_allowed_target_types(
            data_dict.get('allowed_target_types')
        )
        
        # 检查是否重复（同一知识库内）
        kb_id = data_dict.get('kb_id')
        if kb_id:
            stmt = select(Tag).where(
                and_(
                    Tag.tenant_id == current_user.tenant_id,
                    Tag.kb_id == kb_id,
                    Tag.name == tag_name
                )
            )
            result = await use_session.execute(stmt)
            existing_tag = result.scalar_one_or_none()
            
            if existing_tag:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"标签 '{tag_name}' 已存在"
                )
        
        # 调用父类的创建方法
        return await super().create(data_dict, current_user)
    
    async def update(
        self,
        resource_id: UUID,
        data: TagUpdate | Dict[str, Any],
        current_user: User,
        session: Optional[AsyncSession] = None
    ) -> Tag:
        """
        更新标签（带重复检查）
        
        Args:
            resource_id: 标签ID
            data: 更新数据
            current_user: 当前用户
            session: 数据库会话
            
        Returns:
            更新后的标签对象
            
        Raises:
            HTTPException: 如果标签名重复
        """
        # 转换为字典
        if hasattr(data, 'model_dump'):
            data_dict = data.model_dump(exclude_unset=True)
        else:
            data_dict = dict(data)
        
        use_session = session or self.db
        
        # 如果更新了名称，检查重复
        if 'name' in data_dict:
            tag_name = data_dict['name'].strip()
            if not tag_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="标签名称不能为空"
                )
            
            if len(tag_name) > 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="标签名称不能超过 100 个字符"
                )
            
            data_dict['name'] = tag_name
            
            # 获取当前标签
            current_tag = await use_session.get(Tag, resource_id)
            if not current_tag:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="标签不存在"
                )
            
            # 检查是否与其他标签重复
            if current_tag.kb_id:
                stmt = select(Tag).where(
                    and_(
                        Tag.tenant_id == current_user.tenant_id,
                        Tag.kb_id == current_tag.kb_id,
                        Tag.name == tag_name,
                        Tag.id != resource_id  # 排除自己
                    )
                )
                result = await use_session.execute(stmt)
                existing_tag = result.scalar_one_or_none()
                
                if existing_tag:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"标签 '{tag_name}' 已存在"
                    )

        if 'allowed_target_types' in data_dict:
            normalized_allowed_target_types = self._normalize_allowed_target_types(
                data_dict.get('allowed_target_types')
            )
            data_dict['allowed_target_types'] = normalized_allowed_target_types

            current_target_types_stmt = select(distinct(ResourceTag.target_type)).where(
                and_(
                    ResourceTag.tenant_id == current_user.tenant_id,
                    ResourceTag.tag_id == resource_id,
                    ResourceTag.action == "add",
                )
            )
            current_target_types_rows = await use_session.execute(current_target_types_stmt)
            used_target_types = {
                row[0]
                for row in current_target_types_rows.all()
                if row[0] in ALLOWED_TAG_TARGET_TYPES
            }

            removed_target_types = sorted(used_target_types - set(normalized_allowed_target_types))
            if removed_target_types:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "标签当前仍在这些对象上被使用，不能移除对应适用范围："
                        f"{', '.join(removed_target_types)}。"
                        "请先解除绑定后再修改。"
                    )
                )
        
        # 调用父类的更新方法
        return await super().update(resource_id, data_dict, current_user)

    async def delete(
        self,
        resource_id: UUID,
        current_user: Optional[User] = None,
        soft_delete: bool = True
    ) -> None:
        """
        删除标签前执行使用检查。

        设计原则：
        - 只要标签仍被知识库、知识库文档或文件夹使用，就禁止删除
        - 删除限制必须放在后端，避免绕过前端直接调接口误删
        """
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="删除标签需要登录态"
            )

        # 先校验标签归属和访问权限，确保不会读取到其它租户的数据。
        await self.get_by_id(
            resource_id,
            current_user.tenant_id,
            current_user.id,
            check_permission=True,
        )

        kb_count_stmt = select(func.count(distinct(ResourceTag.target_id))).where(
            and_(
                ResourceTag.tenant_id == current_user.tenant_id,
                ResourceTag.tag_id == resource_id,
                ResourceTag.target_type == TARGET_TYPE_KB,
                ResourceTag.action == "add",
            )
        )
        kb_doc_count_stmt = select(func.count(distinct(ResourceTag.target_id))).where(
            and_(
                ResourceTag.tenant_id == current_user.tenant_id,
                ResourceTag.tag_id == resource_id,
                ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                ResourceTag.action == "add",
            )
        )
        folder_count_stmt = select(func.count(distinct(ResourceTag.target_id))).where(
            and_(
                ResourceTag.tenant_id == current_user.tenant_id,
                ResourceTag.tag_id == resource_id,
                ResourceTag.target_type == TARGET_TYPE_FOLDER,
                ResourceTag.action == "add",
            )
        )

        kb_count = int((await self.db.execute(kb_count_stmt)).scalar() or 0)
        kb_doc_count = int((await self.db.execute(kb_doc_count_stmt)).scalar() or 0)
        folder_count = int((await self.db.execute(folder_count_stmt)).scalar() or 0)

        if kb_count > 0 or kb_doc_count > 0 or folder_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"标签仍被使用，暂时不能删除："
                    f"{kb_count} 个知识库、{kb_doc_count} 个文档、{folder_count} 个文件夹正在使用。"
                    f"请先解除绑定后再删除。"
                )
            )

        await super().delete(resource_id, current_user, soft_delete=False)
