"""
文件夹服务

处理文件夹的业务逻辑，包括 ltree 路径生成
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.base_service import BaseService
from models.folder import Folder
from models.user import User
from schemas.folder import FolderCreate, FolderUpdate


class FolderService(BaseService[Folder, FolderCreate, FolderUpdate]):
    """文件夹服务"""
    
    async def get_tree(
        self,
        kb_id: UUID,
        current_user: User,
        session: Optional[AsyncSession] = None
    ) -> List[Folder]:
        """
        获取知识库的完整文件夹树（不分页）
        
        用于前端展示文件夹树，返回所有文件夹
        """
        use_session = session or self.db
        
        stmt = select(Folder).where(
            Folder.tenant_id == current_user.tenant_id,
            Folder.kb_id == kb_id
        ).order_by(Folder.path)
        
        result = await use_session.execute(stmt)
        return result.scalars().all()
    
    async def create(
        self,
        data: FolderCreate,
        current_user: User,
        session: Optional[AsyncSession] = None
    ) -> Folder:
        """
        创建文件夹
        
        自动生成 ltree 路径和层级深度
        """
        use_session = session or self.db
        
        # 生成 ltree 路径和层级
        if data.parent_id:
            # 查询父文件夹
            parent = await use_session.get(Folder, data.parent_id)
            if not parent:
                raise ValueError("父文件夹不存在")
            
            # 验证租户一致性
            if parent.tenant_id != current_user.tenant_id:
                raise ValueError("父文件夹不属于当前租户")
            
            # 生成路径：父路径.当前ID
            # 注意：需要先创建对象获取 ID，然后更新路径
            folder = Folder(
                tenant_id=current_user.tenant_id,
                owner_id=current_user.id,
                kb_id=data.kb_id,
                parent_id=data.parent_id,
                name=data.name,
                summary=data.summary,
                path="temp",  # 临时路径
                level=parent.level + 1,
                created_by_id=current_user.id,
                created_by_name=current_user.nickname or current_user.username,
            )
            use_session.add(folder)
            await use_session.flush()  # 获取 ID
            
            # 更新路径：父路径.f_当前ID (UUID hex 格式)
            folder.path = f"{parent.path}.f_{folder.id.hex}"
            # 更新全路径名称：父全路径 / 当前名称
            folder.full_name_path = f"{parent.full_name_path or ''}/{folder.name}"
        else:
            # 根文件夹
            folder = Folder(
                tenant_id=current_user.tenant_id,
                owner_id=current_user.id,
                kb_id=data.kb_id,
                parent_id=None,
                name=data.name,
                summary=data.summary,
                path="temp",  # 临时路径
                level=1,
                created_by_id=current_user.id,
                created_by_name=current_user.nickname or current_user.username,
            )
            use_session.add(folder)
            await use_session.flush()  # 获取 ID
            
            # 更新路径：使用知识库ID作为根路径，使用 UUID hex 格式并加前缀
            if data.kb_id:
                folder.path = f"kb_{data.kb_id.hex}.f_{folder.id.hex}"
            else:
                folder.path = f"root.f_{folder.id.hex}"
            # 根文件夹全路径名称：/当前名称
            folder.full_name_path = f"/{folder.name}"
        
        # 更新标签
        if data.tags is not None:
            await self._update_tags(
                folder_id=folder.id,
                kb_id=data.kb_id,
                tag_names=data.tags,
                current_user=current_user,
                session=use_session
            )
        
        await use_session.commit()
        await use_session.refresh(folder)
        return folder
    
    async def update(
        self,
        resource_id: UUID,
        data: FolderUpdate,
        current_user: User,
        session: Optional[AsyncSession] = None
    ) -> Folder:
        """
        更新文件夹
        
        如果修改了 parent_id，需要重新计算路径
        """
        use_session = session or self.db
        
        # 获取文件夹
        folder = await use_session.get(Folder, resource_id)
        if not folder:
            raise ValueError("文件夹不存在")
        
        # 验证租户
        if folder.tenant_id != current_user.tenant_id:
            raise ValueError("无权限操作此文件夹")
        
        # 更新基本字段
        old_name = folder.name
        if data.name is not None:
            folder.name = data.name
        if data.summary is not None:
            folder.summary = data.summary
        
        # 如果名称改变且没有移动，也需要更新自己的全路径和子文件夹的全路径
        name_changed = data.name is not None and data.name != old_name
        
        # 如果修改了父文件夹，需要重新计算路径
        if data.parent_id is not None and data.parent_id != folder.parent_id:
            if data.parent_id:
                # 查询新父文件夹
                new_parent = await use_session.get(Folder, data.parent_id)
                if not new_parent:
                    raise ValueError("新父文件夹不存在")
                
                # 验证租户一致性
                if new_parent.tenant_id != current_user.tenant_id:
                    raise ValueError("新父文件夹不属于当前租户")
                
                # 防止循环引用（不能将文件夹移动到自己的子文件夹下）
                if new_parent.path.startswith(folder.path):
                    raise ValueError("不能将文件夹移动到自己的子文件夹下")
                
                # 更新路径和层级：父路径.f_当前ID (UUID hex 格式)
                old_path = folder.path
                old_full_name_path = folder.full_name_path
                folder.parent_id = data.parent_id
                folder.path = f"{new_parent.path}.f_{folder.id.hex}"
                folder.full_name_path = f"{new_parent.full_name_path or ''}/{folder.name}"
                folder.level = new_parent.level + 1
                
                # 更新所有子文件夹的路径和名称路径
                await self._update_children_paths(use_session, old_path, folder.path, old_full_name_path, folder.full_name_path)
            else:
                # 移动到根目录：使用 UUID hex 格式并加前缀
                old_path = folder.path
                old_full_name_path = folder.full_name_path
                folder.parent_id = None
                if folder.kb_id:
                    folder.path = f"kb_{folder.kb_id.hex}.f_{folder.id.hex}"
                else:
                    folder.path = f"root.f_{folder.id.hex}"
                folder.full_name_path = f"/{folder.name}"
                folder.level = 1
                
                # 更新所有子文件夹的路径和名称路径
                await self._update_children_paths(use_session, old_path, folder.path, old_full_name_path, folder.full_name_path)
        elif name_changed:
            # 仅仅是重命名，没改变父级
            old_full_name_path = folder.full_name_path
            # 如果是根目录
            if not folder.parent_id:
                folder.full_name_path = f"/{folder.name}"
            else:
                # 获取父级，重新拼接
                parent = await use_session.get(Folder, folder.parent_id)
                folder.full_name_path = f"{parent.full_name_path or ''}/{folder.name}"
            
            # 更新子节点
            await self._update_children_paths(use_session, folder.path, folder.path, old_full_name_path, folder.full_name_path)
        
        # 更新审计字段
        folder.updated_by_id = current_user.id
        folder.updated_by_name = current_user.nickname or current_user.username
        
        # 更新标签
        if data.tags is not None:
            await self._update_tags(
                folder_id=folder.id,
                kb_id=folder.kb_id,
                tag_names=data.tags,
                current_user=current_user,
                session=use_session
            )
        
        await use_session.commit()
        await use_session.refresh(folder)
        return folder
    
    async def delete(
        self,
        resource_id: UUID,
        current_user: User,
        session: Optional[AsyncSession] = None
    ) -> dict:
        """
        安全删除文件夹（只能删除空文件夹）
        
        检查逻辑：
        1. 检查当前文件夹是否有文档
        2. 检查所有子文件夹是否有文档
        3. 如果有任何文档，阻止删除并返回详细信息
        4. 如果都是空的，级联删除所有子文件夹
        
        Returns:
            删除统计信息
            
        Raises:
            ValueError: 文件夹不为空，无法删除
        """
        use_session = session or self.db
        
        # 获取文件夹
        folder = await use_session.get(Folder, resource_id)
        if not folder:
            raise ValueError("文件夹不存在")
        
        # 验证权限
        if folder.tenant_id != current_user.tenant_id:
            raise ValueError("无权限操作此文件夹")
        
        # 1. 查询所有子文件夹（包括当前文件夹）
        from sqlalchemy import text, func, or_
        stmt = select(Folder).where(
            Folder.tenant_id == current_user.tenant_id,
            or_(
                Folder.id == resource_id,  # 当前文件夹
                text(f"path ~ '{folder.path}.*'::lquery")  # 所有子文件夹
            )
        )
        result = await use_session.execute(stmt)
        all_folders = result.scalars().all()
        folder_ids = [f.id for f in all_folders]
        
        # 2. 检查是否有文档
        # 使用原生 SQL 查询，避免动态加载表结构的同步操作
        from sqlalchemy import text
        
        sql = text("""
            SELECT folder_id, COUNT(*) as doc_count
            FROM knowledge_base_documents
            WHERE tenant_id = :tenant_id
              AND folder_id = ANY(:folder_ids)
            GROUP BY folder_id
        """)
        
        result = await use_session.execute(
            sql,
            {
                "tenant_id": str(current_user.tenant_id),
                "folder_ids": [str(fid) for fid in folder_ids]
            }
        )
        folder_doc_counts = result.all()
        
        # 3. 如果有文档，阻止删除
        if folder_doc_counts:
            # 构建详细的错误信息
            non_empty_folders = []
            for folder_id, doc_count in folder_doc_counts:
                f = next((f for f in all_folders if f.id == folder_id), None)
                if f:
                    non_empty_folders.append({
                        "name": f.name,
                        "doc_count": doc_count
                    })
            
            # 抛出异常，包含详细信息
            error_msg = "无法删除文件夹，以下文件夹包含文档：\n"
            for f in non_empty_folders[:5]:  # 最多显示 5 个
                error_msg += f"- {f['name']} ({f['doc_count']} 个文档)\n"
            
            if len(non_empty_folders) > 5:
                error_msg += f"... 还有 {len(non_empty_folders) - 5} 个文件夹\n"
            
            error_msg += "\n请先删除所有文档后再删除文件夹。"
            
            raise ValueError(error_msg)
        
        # 4. 所有文件夹都是空的，可以删除
        # 按层级从深到浅删除
        all_folders.sort(key=lambda f: f.level, reverse=True)
        
        for f in all_folders:
            await use_session.delete(f)
        
        await use_session.commit()
        
        return {
            "folders_deleted": len(all_folders),
            "message": f"成功删除 {len(all_folders)} 个文件夹"
        }
    
    async def _update_children_paths(
        self,
        session: AsyncSession,
        old_parent_path: str,
        new_parent_path: str,
        old_parent_full_name_path: Optional[str] = None,
        new_parent_full_name_path: Optional[str] = None
    ) -> None:
        """
        递归更新所有子文件夹的路径和全路径名称
        
        使用 ltree 的 subpath 和 replace 功能
        """
        from sqlalchemy import text
        
        # 查询所有子文件夹
        stmt = select(Folder).where(
            text(f"path ~ '{old_parent_path}.*'::lquery"),
            Folder.path != old_parent_path
        )
        result = await session.execute(stmt)
        children = result.scalars().all()
        
        # 更新路径
        for child in children:
            # 1. 替换 ID 路径前缀
            if old_parent_path != new_parent_path:
                child.path = child.path.replace(old_parent_path, new_parent_path, 1)
                # 重新计算层级
                child.level = len(child.path.split('.'))
            
            # 2. 替换全名称路径前缀
            if old_parent_full_name_path and new_parent_full_name_path and child.full_name_path:
                child.full_name_path = child.full_name_path.replace(old_parent_full_name_path, new_parent_full_name_path, 1)
        
    async def _update_tags(
        self,
        folder_id: UUID,
        kb_id: Optional[UUID],
        tag_names: List[str],
        current_user: User,
        session: AsyncSession
    ) -> None:
        """
        更新文件夹关联的标签
        
        逻辑：
        1. 获取文件夹当前关联的所有标签
        2. 计算需要新增和移除的标签
        3. 对新增标签：如果标签不存在则创建，然后建立关联
        4. 对移除标签：删除关联记录
        """
        from models.tag import Tag
        from models.resource_tag import ResourceTag
        from sqlalchemy import delete

        # 1. 查询当前已有的标签关联
        stmt = select(ResourceTag).where(
            ResourceTag.target_id == folder_id,
            ResourceTag.target_type == "folder",
            ResourceTag.tenant_id == current_user.tenant_id
        )
        result = await session.execute(stmt)
        existing_relations = result.scalars().all()
        
        # 获取当前所有的标签名称及对应的记录
        if existing_relations:
            tag_ids = [rel.tag_id for rel in existing_relations]
            stmt = select(Tag).where(Tag.id.in_(tag_ids))
            result = await session.execute(stmt)
            existing_tags = result.scalars().all()
            existing_tag_names = [t.name for t in existing_tags]
            tag_name_to_id = {t.name: t.id for t in existing_tags}
        else:
            existing_tag_names = []
            tag_name_to_id = {}

        # 计算差异
        target_tag_names = [name.strip() for name in tag_names if name.strip()]
        names_to_add = set(target_tag_names) - set(existing_tag_names)
        names_to_remove = set(existing_tag_names) - set(target_tag_names)

        # 2. 处理移除
        if names_to_remove:
            ids_to_remove = [tag_name_to_id[name] for name in names_to_remove]
            delete_stmt = delete(ResourceTag).where(
                ResourceTag.target_id == folder_id,
                ResourceTag.target_type == "folder",
                ResourceTag.tag_id.in_(ids_to_remove),
                ResourceTag.tenant_id == current_user.tenant_id
            )
            await session.execute(delete_stmt)

        # 3. 处理新增
        for name in names_to_add:
            # 3.1 查找或创建标签
            tag_stmt = select(Tag).where(
                Tag.name == name,
                Tag.tenant_id == current_user.tenant_id,
                Tag.kb_id == kb_id
            )
            tag_result = await session.execute(tag_stmt)
            tag = tag_result.scalar_one_or_none()
            
            if not tag:
                # 创建新标签
                tag = Tag(
                    tenant_id=current_user.tenant_id,
                    name=name,
                    kb_id=kb_id,
                    created_by_id=current_user.id,
                    created_by_name=current_user.nickname or current_user.username
                )
                session.add(tag)
                await session.flush()
            
            # 3.2 建立关联
            rel = ResourceTag(
                tenant_id=current_user.tenant_id,
                tag_id=tag.id,
                target_id=folder_id,
                target_type="folder",
                kb_id=kb_id,
                created_by_id=current_user.id,
                created_by_name=current_user.nickname or current_user.username
            )
            session.add(rel)
        
        await session.flush()
