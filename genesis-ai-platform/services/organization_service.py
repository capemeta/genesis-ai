"""
组织架构服务
提供组织的增删改查和树形结构操作
"""
from typing import List, Tuple, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from core.base_service import BaseService
from models.organization import Organization
from models.user import User
from schemas.organization import OrganizationCreate, OrganizationUpdate


class OrganizationService(BaseService[Organization, OrganizationCreate, OrganizationUpdate]):
    """
    组织架构服务
    
    功能：
    - 支持部门名称的模糊搜索
    - 支持状态过滤
    - 树形结构构建
    - ltree 路径维护
    - 软删除支持
    """
    
    async def list_organizations(
        self,
        tenant_id: UUID,
        name: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> List[Organization]:
        """
        获取组织列表（扁平结构，用于前端构建树）
        
        Args:
            tenant_id: 租户ID
            name: 部门名称（模糊搜索）
            status_filter: 状态过滤（0-正常，1-停用）
            
        Returns:
            组织列表
        """
        # 基础查询条件：租户隔离 + 未删除
        conditions = [
            Organization.tenant_id == tenant_id,
            Organization.del_flag == '0'
        ]
        
        # 名称搜索
        if name:
            conditions.append(Organization.name.ilike(f"%{name}%"))
        
        # 状态过滤
        if status_filter:
            conditions.append(Organization.status == status_filter)
        
        # 查询
        stmt = select(Organization).where(*conditions).order_by(
            Organization.parent_id.nullsfirst(),
            Organization.order_num.asc(),
            Organization.created_at.asc()
        )
        
        result = await self.db.execute(stmt)
        organizations = result.scalars().all()
        
        return list(organizations)
    
    async def get_organization_tree(
        self,
        tenant_id: UUID,
        status_filter: Optional[str] = '0'
    ) -> List[Dict[str, Any]]:
        """
        获取组织树形结构（用于下拉选择器）
        
        Args:
            tenant_id: 租户ID
            status_filter: 状态过滤，默认只获取正常状态
            
        Returns:
            树形结构列表
        """
        # 查询条件
        conditions = [
            Organization.tenant_id == tenant_id,
            Organization.del_flag == '0'
        ]
        
        if status_filter:
            conditions.append(Organization.status == status_filter)
        
        # 查询所有符合条件的组织
        stmt = select(Organization).where(*conditions).order_by(
            Organization.order_num.asc(),
            Organization.created_at.asc()
        )
        
        result = await self.db.execute(stmt)
        organizations = result.scalars().all()
        
        # 构建树形结构
        return self._build_tree(organizations)
    
    def _build_tree(self, organizations: List[Organization]) -> List[Dict[str, Any]]:
        """
        将扁平列表构建为树形结构
        
        Args:
            organizations: 组织列表
            
        Returns:
            树形结构
        """
        # 转换为字典
        org_dict = {}
        for org in organizations:
            org_id = str(org.id)
            org_dict[org_id] = {
                "id": org.id,
                "parent_id": org.parent_id,
                "name": org.name,
                "order_num": org.order_num,
                "status": org.status,
                "level": org.level,
                "children": []
            }
        
        # 构建树关系
        root_nodes = []
        for org_id, org_data in org_dict.items():
            parent_id = str(org_data["parent_id"]) if org_data["parent_id"] else None
            if parent_id and parent_id in org_dict:
                org_dict[parent_id]["children"].append(org_data)
            else:
                root_nodes.append(org_data)
        
        # 递归排序
        def sort_children(nodes):
            nodes.sort(key=lambda x: (x["order_num"], x["name"]))
            for node in nodes:
                if node["children"]:
                    sort_children(node["children"])
        
        sort_children(root_nodes)
        return root_nodes
    
    async def get_organization(
        self,
        org_id: UUID,
        tenant_id: UUID
    ) -> Organization:
        """
        获取单个组织详情
        
        Args:
            org_id: 组织ID
            tenant_id: 租户ID
            
        Returns:
            组织实体
        """
        stmt = select(Organization).where(
            Organization.id == org_id,
            Organization.tenant_id == tenant_id,
            Organization.del_flag == '0'
        )
        
        result = await self.db.execute(stmt)
        org = result.scalar_one_or_none()
        
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="组织不存在"
            )
        
        return org
    
    async def create_organization(
        self,
        data: OrganizationCreate,
        tenant_id: UUID,
        current_user: Optional[User] = None
    ) -> Organization:
        """
        创建组织
        
        Args:
            data: 创建数据
            tenant_id: 租户ID
            current_user: 当前用户
            
        Returns:
            创建的组织
        """
        # 生成新ID
        new_id = uuid4()
        
        # 计算 level 和 path
        level = 1
        path = str(new_id).replace('-', '_')  # ltree 不支持连字符
        
        if data.parent_id:
            # 验证父部门存在
            parent = await self.get_organization(data.parent_id, tenant_id)
            level = parent.level + 1
            path = f"{parent.path}.{str(new_id).replace('-', '_')}"
        
        # 创建组织对象
        org = Organization(
            id=new_id,
            tenant_id=tenant_id,
            parent_id=data.parent_id,
            name=data.name,
            description=data.description,
            path=path,
            level=level,
            order_num=data.order_num,
            status=data.status,
            del_flag='0',
            leader_name=data.leader_name,
            phone=data.phone,
            email=data.email,
            limits={}
        )
        
        # 设置审计字段
        if current_user:
            org.created_by_id = current_user.id
            org.created_by_name = current_user.nickname or current_user.username
            org.updated_by_id = current_user.id
            org.updated_by_name = current_user.nickname or current_user.username
        
        org.created_at = datetime.now(timezone.utc)
        org.updated_at = datetime.now(timezone.utc)
        
        self.db.add(org)
        await self.db.commit()
        await self.db.refresh(org)
        
        return org
    
    async def update_organization(
        self,
        data: OrganizationUpdate,
        tenant_id: UUID,
        current_user: Optional[User] = None
    ) -> Organization:
        """
        更新组织
        
        Args:
            data: 更新数据
            tenant_id: 租户ID
            current_user: 当前用户
            
        Returns:
            更新后的组织
        """
        # 获取组织
        org = await self.get_organization(data.id, tenant_id)
        
        # 如果修改了父部门，需要校验和更新路径
        if data.parent_id is not None and data.parent_id != org.parent_id:
            # 不能将自己设为父部门
            if data.parent_id == org.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="不能将部门设为自己的上级"
                )
            
            # 检查是否存在循环引用（不能将子部门设为父部门）
            if data.parent_id:
                await self._check_circular_reference(org.id, data.parent_id, tenant_id)
            
            # 计算新的 level 和 path
            old_path = org.path
            if data.parent_id:
                parent = await self.get_organization(data.parent_id, tenant_id)
                new_level = parent.level + 1
                new_path = f"{parent.path}.{str(org.id).replace('-', '_')}"
            else:
                new_level = 1
                new_path = str(org.id).replace('-', '_')
            
            # 更新所有子部门的路径
            await self._update_children_path(org.id, old_path, new_path, tenant_id)
            
            org.parent_id = data.parent_id
            org.level = new_level
            org.path = new_path
        
        # 更新其他字段
        if data.name is not None:
            org.name = data.name
        if data.description is not None:
            org.description = data.description
        if data.order_num is not None:
            org.order_num = data.order_num
        if data.status is not None:
            org.status = data.status
            
            # 如果状态改为停用且需要级联停用子部门
            if data.status == '1' and data.cascade_disable:
                await self._cascade_disable_children(org.id, tenant_id, current_user)
        
        if data.leader_name is not None:
            org.leader_name = data.leader_name
        if data.phone is not None:
            org.phone = data.phone
        if data.email is not None:
            org.email = data.email
        
        # 更新审计字段
        if current_user:
            org.updated_by_id = current_user.id
            org.updated_by_name = current_user.nickname or current_user.username
        org.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(org)
        
        return org
    
    async def _check_circular_reference(
        self,
        org_id: UUID,
        new_parent_id: UUID,
        tenant_id: UUID
    ) -> None:
        """
        检查是否存在循环引用
        
        Args:
            org_id: 当前组织ID
            new_parent_id: 新的父部门ID
            tenant_id: 租户ID
        """
        # 获取当前组织的所有子部门ID
        children_ids = await self._get_all_children_ids(org_id, tenant_id)
        
        if new_parent_id in children_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能将子部门设为上级部门，这会产生循环引用"
            )
    
    async def _get_all_children_ids(
        self,
        org_id: UUID,
        tenant_id: UUID
    ) -> List[UUID]:
        """
        获取所有子部门ID（递归）
        
        Args:
            org_id: 组织ID
            tenant_id: 租户ID
            
        Returns:
            子部门ID列表
        """
        # 获取当前组织的路径
        org = await self.get_organization(org_id, tenant_id)
        
        # 使用 ltree 查询所有子部门（路径以当前组织路径开头）
        from sqlalchemy import text
        stmt = select(Organization.id).where(
            Organization.tenant_id == tenant_id,
            Organization.del_flag == '0',
            Organization.id != org_id,
            # 使用 ltree 的 <@ 操作符查询子树
            text(f"path <@ '{org.path}'")
        )
        
        result = await self.db.execute(stmt)
        return [row[0] for row in result.fetchall()]
    
    async def _update_children_path(
        self,
        org_id: UUID,
        old_path: str,
        new_path: str,
        tenant_id: UUID
    ) -> None:
        """
        更新所有子部门的路径
        
        Args:
            org_id: 组织ID
            old_path: 旧路径
            new_path: 新路径
            tenant_id: 租户ID
        """
        from sqlalchemy import text, update
        
        # 查询所有子部门
        stmt = select(Organization).where(
            Organization.tenant_id == tenant_id,
            Organization.del_flag == '0',
            Organization.id != org_id,
            text(f"path <@ '{old_path}'")
        )
        
        result = await self.db.execute(stmt)
        children = result.scalars().all()
        
        # 更新每个子部门的路径
        for child in children:
            # 替换路径前缀
            child.path = child.path.replace(old_path, new_path, 1)
            # 重新计算层级
            child.level = len(child.path.split('.'))
        
        await self.db.flush()
    
    async def _cascade_disable_children(
        self,
        org_id: UUID,
        tenant_id: UUID,
        current_user: Optional[User] = None
    ) -> None:
        """
        级联停用所有子部门
        
        Args:
            org_id: 组织ID
            tenant_id: 租户ID
            current_user: 当前用户
        """
        from sqlalchemy import text
        
        # 获取当前组织的路径
        org = await self.get_organization(org_id, tenant_id)
        
        # 使用 ltree 查询所有子部门
        stmt = select(Organization).where(
            Organization.tenant_id == tenant_id,
            Organization.del_flag == '0',
            Organization.id != org_id,
            text(f"path <@ '{org.path}'")
        )
        
        result = await self.db.execute(stmt)
        children = result.scalars().all()
        
        # 更新所有子部门的状态为停用
        for child in children:
            child.status = '1'
            
            # 更新审计字段
            if current_user:
                child.updated_by_id = current_user.id
                child.updated_by_name = current_user.nickname or current_user.username
            child.updated_at = datetime.now(timezone.utc)
        
        await self.db.flush()
    
    async def delete_organization(
        self,
        org_id: UUID,
        tenant_id: UUID,
        current_user: Optional[User] = None
    ) -> bool:
        """
        删除组织（软删除）
        
        Args:
            org_id: 组织ID
            tenant_id: 租户ID
            current_user: 当前用户
            
        Returns:
            是否成功
        """
        # 获取组织
        org = await self.get_organization(org_id, tenant_id)
        
        # 检查是否有子部门
        stmt = select(func.count()).select_from(Organization).where(
            Organization.parent_id == org_id,
            Organization.tenant_id == tenant_id,
            Organization.del_flag == '0'
        )
        children_count = await self.db.scalar(stmt)
        
        if children_count and children_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该部门下存在子部门，无法删除"
            )
        
        # 检查是否有关联用户
        stmt = select(func.count()).select_from(User).where(
            User.organization_id == org_id,
            User.tenant_id == tenant_id
        )
        users_count = await self.db.scalar(stmt)
        
        if users_count and users_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"该部门下存在 {users_count} 个用户，无法删除"
            )
        
        # 软删除
        org.del_flag = '1'
        
        # 更新审计字段
        if current_user:
            org.updated_by_id = current_user.id
            org.updated_by_name = current_user.nickname or current_user.username
        org.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        return True
