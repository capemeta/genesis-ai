"""
权限服务
处理权限相关业务逻辑，包括菜单权限和功能权限
"""
from typing import List, Dict, Any, Optional, cast
from uuid import UUID as PyUUID
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging

from models.permission import Permission
from models.role import Role
from models.user import User
from models.audit_log import AuditLog
from core.config.constants import SUPER_ADMIN_ROLE, ALL_PERMISSION
from core.exceptions import NotFoundException

logger = logging.getLogger(__name__)


class PermissionService:
    """权限服务 - 统一处理菜单权限和功能权限"""
    
    # 缓存过期时间（秒）
    CACHE_TTL = 3600  # 1小时
    
    def __init__(self, session: AsyncSession, redis_client=None):
        self.session = session
        self.redis = redis_client
    
    # ==================== 缓存管理 ====================
    
    def _get_menu_cache_key(self, user_id: PyUUID, tenant_id: PyUUID) -> str:
        """生成菜单缓存键"""
        return f"menu:user:{user_id}:tenant:{tenant_id}"
    
    def _get_permission_cache_key(self, user_id: PyUUID, tenant_id: PyUUID) -> str:
        """生成权限缓存键"""
        return f"permission:user:{user_id}:tenant:{tenant_id}"
    
    async def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """从缓存获取数据"""
        if not self.redis:
            return None
        
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"从缓存读取失败: {e}")
        
        return None
    
    async def _set_to_cache(self, cache_key: str, data: Any) -> None:
        """设置缓存"""
        if not self.redis:
            return
        
        try:
            await self.redis.setex(
                cache_key,
                self.CACHE_TTL,
                json.dumps(data, ensure_ascii=False)
            )
        except Exception as e:
            logger.error(f"设置缓存失败: {e}")
    
    async def clear_user_cache(self, user_id: PyUUID, tenant_id: PyUUID) -> None:
        """清除用户的所有缓存（菜单 + 权限）"""
        if not self.redis:
            return
        
        try:
            menu_key = self._get_menu_cache_key(user_id, tenant_id)
            perm_key = self._get_permission_cache_key(user_id, tenant_id)
            await self.redis.delete(menu_key, perm_key)
            logger.info(f"清除用户缓存: user_id={user_id}, tenant_id={tenant_id}")
        except Exception as e:
            logger.error(f"清除用户缓存失败: {e}")
    
    async def clear_tenant_cache(self, tenant_id: PyUUID) -> None:
        """清除租户所有用户的缓存"""
        if not self.redis:
            return
        
        try:
            # 使用模式匹配删除所有相关缓存
            patterns = [
                f"menu:user:*:tenant:{tenant_id}",
                f"permission:user:*:tenant:{tenant_id}"
            ]
            
            for pattern in patterns:
                cursor = 0
                while True:
                    cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                    if keys:
                        await self.redis.delete(*keys)
                    if cursor == 0:
                        break
            
            logger.info(f"清除租户缓存: tenant_id={tenant_id}")
        except Exception as e:
            logger.error(f"清除租户缓存失败: {e}")
    
    # ==================== 菜单权限 ====================
    
    async def get_user_menu_permissions(
        self,
        user_id: PyUUID,
        tenant_id: PyUUID,
        use_cache: bool = False  # 🔥 默认不使用缓存，直接查询数据库
    ) -> List[Dict[str, Any]]:
        """
        获取用户的菜单权限（直接查询数据库，不使用 Redis 缓存）
        
        逻辑：
        1. 检查用户是否拥有超级管理员角色（code=SUPER_ADMIN_ROLE）
        2. 如果是超管，返回所有菜单权限（type='menu' 或 'directory'）
        3. 如果不是超管，根据用户角色获取对应的菜单权限
        4. 构建树形结构
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            use_cache: 是否使用缓存（默认 False，不推荐使用）
            
        Returns:
            菜单权限列表，包含完整的菜单树结构
        """
        logger.info(f"查询用户菜单权限: user_id={user_id}, tenant_id={tenant_id}")
        
        # 1. 获取用户的所有角色（包括全局角色和租户角色）
        from models.user_roles import user_roles
        
        user_roles_stmt = select(Role).join(
            user_roles,
            Role.id == user_roles.c.role_id
        ).where(
            user_roles.c.user_id == user_id,
            user_roles.c.tenant_id == tenant_id
            # user_roles 表已经记录了用户在当前租户的角色分配
            # JOIN 会自动关联到全局角色（tenant_id IS NULL）或租户角色
        )
        
        result = await self.session.execute(user_roles_stmt)
        roles = result.scalars().all()
        
        # 2. 检查是否是超级管理员
        is_super_admin = any(role.code == SUPER_ADMIN_ROLE for role in roles)
        
        # 3. 获取菜单权限
        if is_super_admin:
            # 超管获取所有菜单权限
            permissions = await self._get_all_menu_permissions()
        else:
            # 普通用户根据角色获取菜单权限
            role_ids = [role.id for role in roles]
            permissions = await self._get_role_menu_permissions(role_ids, tenant_id)
        
        # 4. 构建树形结构
        menu_tree = self._build_menu_tree(permissions)
        
        logger.info(f"获取菜单权限: user_id={user_id}, is_super_admin={is_super_admin}, count={len(menu_tree)}")
        
        return menu_tree
    
    async def _get_all_menu_permissions(self) -> List[Permission]:
        """
        获取所有菜单权限（超管使用）
        
        Returns:
            所有类型为 menu 或 directory 的权限（仅返回正常状态的权限）
        """
        stmt = select(Permission).where(
            Permission.type.in_(['menu', 'directory']),
            Permission.status == 0  # 只返回正常状态的权限
        ).order_by(
            Permission.sort_order.asc()
        )
        
        result = await self.session.execute(stmt)
        permissions = list(result.scalars().all())
        
        logger.info(f"超管获取所有菜单权限，共 {len(permissions)} 条（仅正常状态）")
        
        return permissions
    
    async def _get_role_menu_permissions(
        self,
        role_ids: List[PyUUID],
        tenant_id: PyUUID
    ) -> List[Permission]:
        """
        根据角色获取菜单权限
        
        Args:
            role_ids: 角色 ID 列表
            tenant_id: 租户 ID
            
        Returns:
            角色拥有的菜单权限列表（仅返回正常状态的权限）
        """
        from models.role_permissions import role_permissions
        
        # 查询角色关联的权限
        stmt = select(Permission).join(
            role_permissions,
            Permission.id == role_permissions.c.permission_id
        ).where(
            role_permissions.c.role_id.in_(role_ids),
            Permission.type.in_(['menu', 'directory']),
            Permission.status == 0  # 只返回正常状态的权限
        ).order_by(
            Permission.sort_order.asc()
        ).distinct()
        
        result = await self.session.execute(stmt)
        permissions = list(result.scalars().all())
        
        logger.info(f"角色 {role_ids} 获取菜单权限，共 {len(permissions)} 条（仅正常状态）")
        
        # 补全父级权限（如果子菜单有权限，父菜单也应该可见）
        permissions_with_parents = await self._add_parent_permissions(permissions)
        
        logger.info(f"补全父级后，共 {len(permissions_with_parents)} 条")
        
        return permissions_with_parents
    
    async def _add_parent_permissions(
        self,
        permissions: List[Permission]
    ) -> List[Permission]:
        """
        补全父级权限（优化版：一次查询获取所有父级）
        
        如果用户有子菜单的权限，需要确保父菜单也可见
        
        Args:
            permissions: 原始权限列表
            
        Returns:
            包含父级权限的完整列表
        """
        if not permissions:
            return permissions
        
        # 收集所有需要的父级 ID
        all_parent_ids = set()
        permission_ids = {p.id for p in permissions}
        
        # 递归收集所有父级 ID
        def collect_parent_ids(perms: List[Permission]):
            for p in perms:
                if p.parent_id and p.parent_id not in permission_ids:
                    all_parent_ids.add(p.parent_id)
        
        collect_parent_ids(permissions)
        
        if not all_parent_ids:
            return permissions
        
        # 一次性查询所有缺失的父级权限
        stmt = select(Permission).where(
            Permission.id.in_(all_parent_ids),
            Permission.status == 0  # 只查询正常状态的父级权限
        )
        
        result = await self.session.execute(stmt)
        parent_permissions = list(result.scalars().all())
        
        # 合并权限列表
        all_permissions = permissions + parent_permissions
        
        # 检查是否还有更上层的父级（递归一次）
        new_parent_ids = {p.parent_id for p in parent_permissions if p.parent_id}
        existing_ids = {p.id for p in all_permissions}
        missing_ids = new_parent_ids - existing_ids
        
        if missing_ids:
            # 查询剩余的父级
            stmt = select(Permission).where(
                Permission.id.in_(missing_ids),
                Permission.status == 0  # 只查询正常状态的父级权限
            )
            result = await self.session.execute(stmt)
            additional_parents = list(result.scalars().all())
            all_permissions.extend(additional_parents)
        
        return all_permissions
    
    def _build_menu_tree(
        self,
        permissions: List[Permission]
    ) -> List[Dict[str, Any]]:
        """
        构建菜单树形结构
        
        Args:
            permissions: 权限列表
            
        Returns:
            树形结构的菜单列表
        """
        # 转换为字典格式（使用字符串 ID 作为 key，保持一致性）
        permission_dict: Dict[str, Dict[str, Any]] = {}
        for perm in permissions:
            perm_id_str = str(perm.id)
            permission_dict[perm_id_str] = {
                "id": perm_id_str,
                "code": perm.code,
                "name": perm.name,
                "type": perm.type,
                "module": perm.module,
                "parent_id": str(perm.parent_id) if perm.parent_id else None,
                "path": perm.path,
                "icon": perm.icon,
                "component": perm.component,
                "sort_order": perm.sort_order,
                "is_hidden": perm.is_hidden,
                "children": []
            }
        
        # 构建树形结构
        root_menus = []
        for perm_id, perm_data in permission_dict.items():
            parent_id = perm_data["parent_id"]
            if parent_id and parent_id in permission_dict:
                # 添加到父节点的 children
                permission_dict[parent_id]["children"].append(perm_data)
            else:
                # 顶级菜单（parent_id 为 None 或不在字典中）
                root_menus.append(perm_data)
        
        # 递归排序
        def sort_children(menu_list):
            menu_list.sort(key=lambda x: x["sort_order"])
            for menu in menu_list:
                if menu["children"]:
                    sort_children(menu["children"])
        
        sort_children(root_menus)
        
        return root_menus
    
    async def check_user_has_permission(
        self,
        user_id: PyUUID,
        tenant_id: PyUUID,
        permission_code: str
    ) -> bool:
        """
        检查用户是否拥有指定权限
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            permission_code: 权限代码
            
        Returns:
            是否拥有权限
        """
        from models.user_roles import user_roles
        
        # 获取用户角色
        user_roles_stmt = select(Role).join(
            user_roles,
            Role.id == user_roles.c.role_id
        ).where(
            user_roles.c.user_id == user_id,
            user_roles.c.tenant_id == tenant_id
        )
        
        result = await self.session.execute(user_roles_stmt)
        roles = result.scalars().all()
        
        # 超管拥有所有权限
        if any(role.code == SUPER_ADMIN_ROLE for role in roles):
            return True
        
        # 检查角色权限
        from models.role_permissions import role_permissions
        
        role_ids = [role.id for role in roles]
        
        stmt = select(Permission).join(
            role_permissions,
            Permission.id == role_permissions.c.permission_id
        ).where(
            role_permissions.c.role_id.in_(role_ids),
            role_permissions.c.tenant_id == tenant_id,
            Permission.code == permission_code,
            Permission.status == 0  # 只检查正常状态的权限
        )
        
        result = await self.session.execute(stmt)
        permission = result.scalar_one_or_none()
        
        return permission is not None
    
    # ==================== 功能权限 ====================
    
    async def get_user_permissions_with_user(
        self,
        user: User,
        use_cache: bool = False
    ) -> List[str]:
        """
        获取用户权限代码集合（带超级管理员判断）
        
        逻辑：
        1. 使用 user.is_super_admin() 判断是否是超级管理员
        2. 如果是超级管理员，返回 ["*:*:*"]（拥有所有权限）
        3. 如果不是超级管理员，查询实际权限
        
        Args:
            user: 用户对象（需要已设置 roles 属性）
            use_cache: 是否使用缓存（默认 False）
            
        Returns:
            权限代码列表，超级管理员返回 ["*:*:*"]，普通用户返回实际权限
        """
        from core.config.constants import ALL_PERMISSION
        
        # 判断是否是超级管理员
        if user.is_super_admin():
            # 超级管理员拥有所有权限
            logger.info(f"User {user.username} (ID: {user.id}) is super admin, granted all permissions: {ALL_PERMISSION}")
            return [ALL_PERMISSION]
        else:
            # 普通用户查询实际权限
            permissions = await self.get_user_permissions(
                user.id,
                user.tenant_id,
                use_cache
            )
            logger.info(f"User {user.username} (ID: {user.id}) permissions count: {len(permissions)}")
            return permissions
    
    async def get_user_permissions(
        self, 
        user_id: PyUUID, 
        tenant_id: PyUUID,
        use_cache: bool = False  # 🔥 默认不使用缓存，直接查询数据库
    ) -> List[str]:
        """
        获取用户的所有权限代码列表（包括菜单权限和功能权限）
        直接查询数据库，不使用 Redis 缓存
        
        逻辑：
        1. 查询用户的所有角色
        2. 查询这些角色的所有权限
        3. 去重返回权限代码列表
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            use_cache: 是否使用缓存（默认 False，不推荐使用）
            
        Returns:
            权限代码列表，如 ["user:create", "user:update", "menu:system"]
        """
        logger.info(f"查询用户权限代码: user_id={user_id}, tenant_id={tenant_id}")
        
        from models.user_roles import user_roles
        from models.role_permissions import role_permissions
        
        # 查询用户角色
        stmt = select(user_roles.c.role_id).where(
            and_(
                user_roles.c.user_id == user_id,
                user_roles.c.tenant_id == tenant_id
            )
        )
        result = await self.session.execute(stmt)
        role_ids = [row[0] for row in result.fetchall()]
        
        if not role_ids:
            return []
        
        # 查询角色权限
        stmt = select(Permission.code).join(
            role_permissions,
            Permission.id == role_permissions.c.permission_id
        ).where(
            and_(
                role_permissions.c.role_id.in_(role_ids),
                Permission.status == 0  # 只返回正常状态的权限
            )
        ).distinct()
        
        result = await self.session.execute(stmt)
        permissions = [row[0] for row in result.fetchall()]
        
        logger.info(f"获取权限代码: user_id={user_id}, count={len(permissions)}")
        
        return permissions
    
    # ==================== 权限管理（CRUD）====================
    
    async def list_permissions(
        self,
        tenant_id: PyUUID,
        search: Optional[str] = None,
        type_filter: Optional[str] = None,
        module_filter: Optional[str] = None,
        status_filter: Optional[int] = None
    ) -> tuple[List[Permission], int]:
        """
        获取权限列表（支持搜索和过滤）
        
        Args:
            tenant_id: 租户 ID
            search: 搜索关键词（模糊匹配 code, name, module）
            type_filter: 权限类型过滤
            module_filter: 模块过滤
            status_filter: 状态过滤
            
        Returns:
            (权限列表, 总数)
        """
        # 基础查询条件：租户隔离（包括全局权限）
        conditions = [
            or_(
                Permission.tenant_id == tenant_id,
                Permission.tenant_id.is_(None)  # 包括全局权限
            )
        ]
        
        # 搜索条件（模糊匹配 code, name, module）
        if search:
            search_pattern = f"%{search}%"
            conditions.append(
                or_(
                    Permission.code.ilike(search_pattern),
                    Permission.name.ilike(search_pattern),
                    Permission.module.ilike(search_pattern)
                )
            )
        
        # 类型过滤
        if type_filter:
            conditions.append(Permission.type == type_filter)
        
        # 模块过滤
        if module_filter:
            conditions.append(Permission.module == module_filter)
        
        # 状态过滤
        if status_filter is not None:
            conditions.append(Permission.status == status_filter)
        
        # 计算总数
        count_stmt = select(func.count()).select_from(Permission).where(*conditions)
        total = await self.session.scalar(count_stmt)
        
        # 查询
        stmt = select(Permission).where(*conditions).order_by(
            Permission.module.asc(),
            Permission.sort_order.asc(),
            Permission.created_at.asc()
        )
        
        result = await self.session.execute(stmt)
        permissions = list(result.scalars().all())
        
        logger.info(f"查询权限列表: tenant_id={tenant_id}, search={search}, count={len(permissions)}")
        
        return permissions, total or 0
    
    async def get_permission(
        self,
        permission_id: PyUUID,
        tenant_id: Optional[PyUUID] = None
    ) -> Permission:
        """
        获取单个权限详情（权限为全局共享，不限租户）
        
        Args:
            permission_id: 权限 ID
            tenant_id: 租户 ID（已废弃，保留参数兼容性）
            
        Returns:
            权限实体
        """
        # 权限为全局共享，只通过 permission_id 查询
        
        logger.info(f"查询权限: permission_id={permission_id}, tenant_id={tenant_id}")
        stmt = select(Permission).where(Permission.id == permission_id)
        
        result = await self.session.execute(stmt)
        permission = result.scalar_one_or_none()
        
        if not permission:
            logger.warning(f"权限不存在: permission_id={permission_id}")
            raise NotFoundException("权限不存在")
        
        logger.info(f"找到权限: id={permission.id}, code={permission.code}, tenant_id={permission.tenant_id}")
        return permission
    
    async def create_permission(
        self,
        data: Dict[str, Any],
        tenant_id: PyUUID,
        current_user: Optional[User] = None
    ) -> Permission:
        """
        创建权限（不设置租户ID，权限为全局共享）
        
        Args:
            data: 创建数据
            tenant_id: 租户 ID（用于权限检查，不存储）
            current_user: 当前用户
            
        Returns:
            创建的权限
        """
        # 检查 code 是否重复（全局检查，不限租户）
        await self._check_code_unique(data['code'], None)
        
        # 创建权限对象（不设置 tenant_id）
        permission = Permission(
            code=data['code'],
            name=data['name'],
            type=data['type'],
            module=data['module'],
            description=data.get('description'),
            status=data.get('status', 0),
            parent_id=data.get('parent_id'),
            path=data.get('path'),
            icon=data.get('icon'),
            component=data.get('component'),
            sort_order=data.get('sort_order', 0),
            is_hidden=data.get('is_hidden', False),
            api_path=data.get('api_path'),
            http_method=data.get('http_method')
        )
        
        # 设置审计字段
        if current_user:
            permission.created_by_id = current_user.id
            permission.created_by_name = current_user.nickname or current_user.username
            permission.updated_by_id = current_user.id
            permission.updated_by_name = current_user.nickname or current_user.username
        
        permission.created_at = datetime.now(timezone.utc)
        permission.updated_at = datetime.now(timezone.utc)
        
        self.session.add(permission)
        await self.session.commit()
        await self.session.refresh(permission)
        
        logger.info(f"创建权限: code={permission.code}, id={permission.id}")
        
        return permission
    
    async def update_permission(
        self,
        permission_id: PyUUID,
        data: Dict[str, Any],
        tenant_id: PyUUID,
        current_user: Optional[User] = None
    ) -> Permission:
        """
        更新权限（支持级联更新子权限状态）
        
        Args:
            permission_id: 权限 ID
            data: 更新数据
            tenant_id: 租户 ID
            current_user: 当前用户
            
        Returns:
            更新后的权限
        """
        # 获取权限
        permission = await self.get_permission(permission_id, tenant_id)
        
        # 如果修改了 code，检查是否重复
        if 'code' in data and data['code'] != permission.code:
            await self._check_code_unique(data['code'], tenant_id, exclude_id=permission_id)
        
        # 检查是否将状态改为停用（1）
        is_disabling = 'status' in data and data['status'] == 1 and permission.status == 0
        child_count = 0
        
        if is_disabling:
            # 查询子权限数量
            stmt = select(func.count()).select_from(Permission).where(
                Permission.parent_id == permission_id
            )
            child_count = await self.session.scalar(stmt) or 0
            
            if child_count > 0:
                logger.info(f"停用权限 {permission.code}，同时将停用 {child_count} 个子权限")
                
                # 递归获取所有子权限 ID
                async def get_all_child_ids(parent_id: PyUUID) -> List[PyUUID]:
                    child_ids = []
                    stmt = select(Permission.id).where(Permission.parent_id == parent_id)
                    result = await self.session.execute(stmt)
                    direct_children = result.scalars().all()
                    
                    for child_id in direct_children:
                        child_ids.append(child_id)
                        # 递归获取子权限的子权限
                        grandchild_ids = await get_all_child_ids(child_id)
                        child_ids.extend(grandchild_ids)
                    
                    return child_ids
                
                # 获取所有子权限 ID
                all_child_ids = await get_all_child_ids(permission_id)
                
                # 批量更新子权限状态
                if all_child_ids:
                    from sqlalchemy import update as sql_update
                    update_stmt = sql_update(Permission).where(
                        Permission.id.in_(all_child_ids)
                    ).values(
                        status=1,
                        updated_by_id=current_user.id if current_user else None,
                        updated_by_name=current_user.nickname or current_user.username if current_user else None,
                        updated_at=datetime.now(timezone.utc)
                    )
                    await self.session.execute(update_stmt)
                    logger.info(f"已批量停用 {len(all_child_ids)} 个子权限")
        
        # 更新字段
        if 'code' in data:
            permission.code = data['code']
        if 'name' in data:
            permission.name = data['name']
        if 'type' in data:
            permission.type = data['type']
        if 'module' in data:
            permission.module = data['module']
        if 'description' in data:
            permission.description = data['description']
        if 'status' in data:
            permission.status = data['status']
        if 'parent_id' in data:
            permission.parent_id = data['parent_id']
        if 'path' in data:
            permission.path = data['path']
        if 'icon' in data:
            permission.icon = data['icon']
        if 'component' in data:
            permission.component = data['component']
        if 'sort_order' in data:
            permission.sort_order = data['sort_order']
        if 'is_hidden' in data:
            permission.is_hidden = data['is_hidden']
        if 'api_path' in data:
            permission.api_path = data['api_path']
        if 'http_method' in data:
            permission.http_method = data['http_method']
        
        # 更新审计字段
        if current_user:
            permission.updated_by_id = current_user.id
            permission.updated_by_name = current_user.nickname or current_user.username
        permission.updated_at = datetime.now(timezone.utc)
        
        await self.session.commit()
        await self.session.refresh(permission)
        
        if is_disabling and child_count > 0:
            logger.info(f"更新权限: code={permission.code}, id={permission.id}, 同时停用了 {child_count} 个子权限")
        else:
            logger.info(f"更新权限: code={permission.code}, id={permission.id}")
        
        return permission
    
    async def delete_permission(
        self,
        permission_id: PyUUID,
        tenant_id: PyUUID
    ) -> bool:
        """
        删除权限（硬删除，级联删除子权限）
        
        Args:
            permission_id: 权限 ID
            tenant_id: 租户 ID
            
        Returns:
            是否成功
        """
        # 获取权限
        permission = await self.get_permission(permission_id, tenant_id)
        
        # 递归获取所有子权限 ID
        async def get_all_child_ids(parent_id: PyUUID) -> List[PyUUID]:
            child_ids = []
            stmt = select(Permission.id).where(Permission.parent_id == parent_id)
            result = await self.session.execute(stmt)
            direct_children = result.scalars().all()
            
            for child_id in direct_children:
                child_ids.append(child_id)
                # 递归获取子权限的子权限
                grandchild_ids = await get_all_child_ids(child_id)
                child_ids.extend(grandchild_ids)
            
            return child_ids
        
        # 获取所有要删除的权限 ID（包括自己和所有子权限）
        all_ids_to_delete = [permission_id]
        child_ids = await get_all_child_ids(permission_id)
        all_ids_to_delete.extend(child_ids)
        
        # 检查是否有角色关联
        from models.role_permissions import role_permissions
        
        stmt = select(func.count()).select_from(role_permissions).where(
            role_permissions.c.permission_id.in_(all_ids_to_delete)
        )
        role_count = await self.session.scalar(stmt)
        
        if role_count and role_count > 0:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"该权限或其子权限已被 {role_count} 个角色使用，无法删除"
            )
        
        # 硬删除所有权限（包括子权限）
        delete_stmt = delete(Permission).where(Permission.id.in_(all_ids_to_delete))
        await self.session.execute(delete_stmt)
        await self.session.commit()
        
        logger.info(f"删除权限及其子权限: code={permission.code}, id={permission_id}, 共删除 {len(all_ids_to_delete)} 个权限")
        
        return True
    
    async def _check_code_unique(
        self,
        code: str,
        tenant_id: Optional[PyUUID] = None,
        exclude_id: Optional[PyUUID] = None
    ) -> None:
        """
        检查权限代码是否唯一（全局检查）
        
        Args:
            code: 权限代码
            tenant_id: 租户 ID（已废弃，保留参数兼容性）
            exclude_id: 排除的权限 ID（用于更新时）
        """
        conditions = [Permission.code == code]
        
        if exclude_id:
            conditions.append(Permission.id != exclude_id)
        
        stmt = select(func.count()).select_from(Permission).where(*conditions)
        count = await self.session.scalar(stmt)
        
        if count and count > 0:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"权限代码 '{code}' 已存在"
            )
    
    async def get_permission_tree(
        self, 
        tenant_id: PyUUID,
        permission_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取权限树（用于上级权限选择）
        
        Args:
            tenant_id: 租户 ID
            permission_type: 权限类型过滤（menu/function/directory）
            
        Returns:
            权限树形结构（仅返回正常状态的权限）
        """
        # 查询所有权限（包括全局权限）
        stmt = select(Permission).where(
            or_(
                Permission.tenant_id == tenant_id,
                Permission.tenant_id.is_(None)  # 包括全局权限
            ),
            Permission.status == 0  # 只返回正常状态的权限
        )
        
        if permission_type:
            stmt = stmt.where(Permission.type == permission_type)
        
        stmt = stmt.order_by(Permission.sort_order.asc())
        
        result = await self.session.execute(stmt)
        permissions = list(result.scalars().all())
        
        # 转换为字典格式
        permission_list: List[Dict[str, Any]] = []
        for perm in permissions:
            permission_list.append({
                "id": str(perm.id),
                "code": perm.code,
                "name": perm.name,
                "type": perm.type,
                "module": perm.module,
                "parent_id": str(perm.parent_id) if perm.parent_id else None,
                "icon": perm.icon,
                "path": perm.path,
                "sort_order": perm.sort_order,
                "status": perm.status,
                "description": perm.description,
                "created_at": perm.created_at.isoformat() if perm.created_at else None
            })
        
        # 构建树形结构
        tree = self._build_tree_structure(permission_list)
        
        return tree
    
    def _build_tree_structure(
        self, 
        permissions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        构建树形结构（递归）
        
        Args:
            permissions: 权限列表
            
        Returns:
            树形结构
        """
        # 创建 ID 到权限的映射
        permission_map = {perm["id"]: {**perm, "children": []} for perm in permissions}
        
        # 构建树形结构
        root_nodes = []
        for perm in permissions:
            parent_id = perm["parent_id"]
            if parent_id and parent_id in permission_map:
                # 添加到父节点的 children
                permission_map[parent_id]["children"].append(permission_map[perm["id"]])
            else:
                # 顶级节点
                root_nodes.append(permission_map[perm["id"]])
        
        # 递归排序
        def sort_tree(nodes):
            nodes.sort(key=lambda x: x["sort_order"])
            for node in nodes:
                if node["children"]:
                    sort_tree(node["children"])
        
        sort_tree(root_nodes)
        
        return root_nodes
    

    async def get_user_permission_tree(
        self,
        user_id: PyUUID,
        tenant_id: PyUUID
    ) -> List[Dict[str, Any]]:
        """
        获取当前用户的权限树（用于角色授权）
        
        只返回当前用户拥有的权限，用于角色授权时限制可分配的权限范围
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            
        Returns:
            当前用户拥有的权限树
        """
        from models.user_roles import user_roles
        from models.role_permissions import role_permissions
        
        # 1. 获取用户的所有角色
        user_roles_stmt = select(Role).join(
            user_roles,
            Role.id == user_roles.c.role_id
        ).where(
            user_roles.c.user_id == user_id,
            user_roles.c.tenant_id == tenant_id
        )
        
        result = await self.session.execute(user_roles_stmt)
        roles = result.scalars().all()
        
        # 2. 检查是否是超级管理员
        is_super_admin = any(role.code == SUPER_ADMIN_ROLE for role in roles)
        
        # 3. 获取权限
        permissions: List[Permission]
        if is_super_admin:
            # 超管获取所有权限
            stmt = select(Permission).where(
                or_(
                    Permission.tenant_id == tenant_id,
                    Permission.tenant_id.is_(None)
                ),
                Permission.status == 0  # 只返回正常状态的权限
            ).order_by(Permission.sort_order.asc())
            
            result = await self.session.execute(stmt)
            permissions = cast(List[Permission], list(result.scalars().all()))
        else:
            # 普通用户根据角色获取权限
            role_ids = [role.id for role in roles]
            
            stmt = select(Permission).join(
                role_permissions,
                Permission.id == role_permissions.c.permission_id
            ).where(
                role_permissions.c.role_id.in_(role_ids),
                Permission.status == 0  # 只返回正常状态的权限
            ).order_by(Permission.sort_order.asc()).distinct()
            
            result = await self.session.execute(stmt)
            permissions = cast(List[Permission], list(result.scalars().all()))
        
        # 4. 转换为字典格式
        permission_list: List[Dict[str, Any]] = []
        for perm in permissions:
            permission_list.append({
                "id": str(perm.id),
                "code": perm.code,
                "name": perm.name,
                "type": perm.type,
                "module": perm.module,
                "parent_id": str(perm.parent_id) if perm.parent_id else None,
                "icon": perm.icon,
                "path": perm.path,
                "sort_order": perm.sort_order,
                "status": perm.status,
                "description": perm.description,
                "created_at": perm.created_at.isoformat() if perm.created_at else None
            })
        
        # 5. 构建树形结构
        tree = self._build_tree_structure(permission_list)
        
        logger.info(f"获取用户权限树: user_id={user_id}, is_super_admin={is_super_admin}, count={len(permissions)}")
        
        return tree

    async def get_role_permissions(self, current_user: User) -> List[str]:
        """
        获取角色数据权限
        
        Args:
            current_user: 当前用户对象
            
        Returns:
            角色权限信息
        """
        return []


    # ==================== 审计日志 ====================
    
    async def log_audit(
        self,
        action: str,
        operator_id: PyUUID,
        tenant_id: PyUUID,
        operator_name: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[PyUUID] = None,
        target_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        记录审计日志（使用统一的 audit_logs 表）
        
        Args:
            action: 操作类型（assign_role, revoke_role, assign_permission, revoke_permission, update_permission）
            operator_id: 操作人ID
            tenant_id: 租户ID
            operator_name: 操作人名称（可选，存储在 detail 中）
            target_type: 目标类型（user, role, permission）
            target_id: 目标对象ID
            target_name: 目标对象名称（可选，存储在 detail 中）
            details: 操作详情（可选，额外信息）
            success: 操作是否成功
            error_message: 错误消息（可选）
            ip_address: IP地址（可选）
            user_agent: User Agent（可选）
        """
        try:
            # 构建 detail 字段
            detail_data = details or {}
            
            # 添加额外信息到 detail
            if operator_name:
                detail_data["operator_name"] = operator_name
            if target_name:
                detail_data["target_name"] = target_name
            if not success:
                detail_data["success"] = False
            if error_message:
                detail_data["error_message"] = error_message
            if user_agent:
                detail_data["user_agent"] = user_agent
            
            # 创建审计日志
            audit_log = AuditLog(
                tenant_id=tenant_id,
                user_id=operator_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                detail=detail_data if detail_data else None,
                ip_address=ip_address
            )
            
            self.session.add(audit_log)
            await self.session.flush()
            
            logger.info(
                f"审计日志: action={action}, operator={operator_name or operator_id}, "
                f"target={target_type}:{target_name or target_id}, success={success}"
            )
        except Exception as e:
            logger.error(f"记录审计日志失败: {e}")
            # 审计日志失败不应该影响主业务流程
    
    async def get_audit_logs(
        self,
        tenant_id: PyUUID,
        operator_id: Optional[PyUUID] = None,
        target_type: Optional[str] = None,
        target_id: Optional[PyUUID] = None,
        action: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[AuditLog], int]:
        """
        查询审计日志（使用统一的 audit_logs 表）
        
        Args:
            tenant_id: 租户ID
            operator_id: 操作人ID（可选）
            target_type: 目标类型（可选）
            target_id: 目标对象ID（可选）
            action: 操作类型（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            page: 页码
            page_size: 每页数量
            
        Returns:
            (审计日志列表, 总数)
        """
        # 构建查询
        stmt = select(AuditLog).where(
            AuditLog.tenant_id == tenant_id
        )
        
        if operator_id:
            stmt = stmt.where(AuditLog.user_id == operator_id)
        
        if target_type:
            stmt = stmt.where(AuditLog.target_type == target_type)
        
        if target_id:
            stmt = stmt.where(AuditLog.target_id == target_id)
        
        if action:
            stmt = stmt.where(AuditLog.action == action)
        
        if start_date:
            stmt = stmt.where(AuditLog.created_at >= start_date)
        
        if end_date:
            stmt = stmt.where(AuditLog.created_at <= end_date)
        
        # 计算总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = int(total_result.scalar() or 0)
        
        # 分页查询
        stmt = stmt.order_by(AuditLog.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.session.execute(stmt)
        logs = list(result.scalars().all())
        
        return logs, total
