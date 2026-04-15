"""
权限系统
定义权限枚举和权限检查依赖
"""
from enum import Enum
from typing import Any, List, TYPE_CHECKING
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from core.security.auth import get_current_user
from core.config.constants import SUPER_ADMIN_ROLE, ALL_PERMISSION
from models.user import User

if TYPE_CHECKING:
    from collections.abc import Callable


class Permission(str, Enum):
    """
    权限枚举
    格式：资源:操作
    
    ⚠️ 废弃警告（Deprecated）：
    
    本枚举类已被标记为废弃，建议使用字符串权限代码代替。
    
    原因：
    1. 枚举定义的权限代码与数据库中的动态权限不一致
    2. 枚举无法支持动态添加的自定义权限
    3. 字符串权限代码更灵活，更易于维护
    
    迁移指南：
    
    旧代码（使用枚举）：
    ```python
    @router.get("/users/")
    async def list_users(
        current_user: User = Depends(require_permissions(Permission.USER_READ))
    ):
        pass
    ```
    
    新代码（使用字符串）：
    ```python
    @router.get("/users/")
    async def list_users(
        current_user: User = Depends(require_permissions("user:read"))
    ):
        pass
    
    # 或使用 CRUD 工厂的权限配置
    crud_factory.register(
        model=User,
        prefix="/users",
        tags=["users"],
        list_permissions=["user:read", "admin"],
        create_permissions=["user:write", "admin"],
    )
    ```
    
    推荐的权限代码格式：
    - 模块级权限：`模块:操作`，如 `user:read`, `user:write`
    - 页面级权限：`模块:页面:操作`，如 `settings:users:list`, `settings:roles:create`
    - 特殊权限：`admin`（管理员），使用 SUPER_ADMIN_ROLE 常量（超级管理员）
    
    注意：本枚举类将保留以确保向后兼容，但不建议在新代码中使用。
    """
    # ==================== 用户权限 ====================
    USER_READ = "user:read"           # 查看用户
    USER_WRITE = "user:write"         # 创建/更新用户
    USER_DELETE = "user:delete"       # 删除用户
    USER_MANAGE = "user:manage"       # 管理用户（包含所有用户权限）
    
    # ==================== 知识库权限 ====================
    KB_READ = "kb:read"               # 查看知识库
    KB_WRITE = "kb:write"             # 创建/更新知识库
    KB_DELETE = "kb:delete"           # 删除知识库
    KB_MANAGE = "kb:manage"           # 管理知识库（包含所有知识库权限）
    
    # ==================== 文档权限 ====================
    DOC_READ = "doc:read"             # 查看文档
    DOC_WRITE = "doc:write"           # 上传/更新文档
    DOC_DELETE = "doc:delete"         # 删除文档
    DOC_MANAGE = "doc:manage"         # 管理文档
    
    # ==================== 对话权限 ====================
    CHAT_READ = "chat:read"           # 查看对话历史
    CHAT_WRITE = "chat:write"         # 发起对话
    CHAT_DELETE = "chat:delete"       # 删除对话
    
    # ==================== 管理员权限 ====================
    ADMIN = "admin"                   # 管理员（租户级别）
    # 注意：超级管理员角色代码应使用 SUPER_ADMIN_ROLE 常量
    
    # ==================== 系统权限 ====================
    SYSTEM_CONFIG = "system:config"   # 系统配置
    SYSTEM_MONITOR = "system:monitor" # 系统监控


class RoleChecker:
    """
    角色检查器
    用作 FastAPI 依赖注入
    """
    
    def __init__(self, required_roles: List[str]):
        """
        初始化角色检查器
        
        Args:
            required_roles: 所需角色列表（满足任一即可）
        """
        self.required_roles = required_roles
    
    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
    ) -> User:
        """
        检查用户是否有所需角色
        
        Args:
            current_user: 当前用户
            
        Returns:
            User: 当前用户
            
        Raises:
            HTTPException: 角色不足
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 超级管理员拥有所有角色
        if current_user.is_superuser:
            return current_user
        
        # 获取用户角色
        user_roles = set(current_user.roles)
        
        # 检查是否有所需角色（满足任一即可）
        for role in self.required_roles:
            if role in user_roles:
                logger.debug(f"用户拥有所需角色: {role}")
                return current_user
        
        # 角色不足
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required roles: {self.required_roles}",
        )


class PermissionChecker:
    """
    权限检查器
    用作 FastAPI 依赖注入
    """
    
    def __init__(self, required_permissions: List[Permission | str]):
        """
        初始化权限检查器
        
        Args:
            required_permissions: 所需权限列表（满足任一即可），可以是 Permission 枚举或字符串
        """
        # 将字符串转换为 Permission 枚举（如果可能）
        self.required_permissions: List[str] = []
        for perm in required_permissions:
            if isinstance(perm, Permission):
                self.required_permissions.append(perm.value)
            else:
                self.required_permissions.append(str(perm))
    
    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
    ) -> User:
        """
        检查用户是否有所需权限
        
        Args:
            current_user: 当前用户
            
        Returns:
            User: 当前用户
            
        Raises:
            HTTPException: 权限不足
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 超级管理员拥有所有权限
        if current_user.is_superuser:
            return current_user
        
        # 获取用户权限
        user_permissions = await self._get_user_permissions(current_user)
        
        # 检查是否拥有 "*:*:*" 超级权限（超级管理员权限）
        if ALL_PERMISSION in user_permissions:
            logger.debug(f"用户拥有超级权限 {ALL_PERMISSION}，允许通过")
            return current_user
        
        # 检查是否有所需权限（满足任一即可）
        for permission in self.required_permissions:
            if permission in user_permissions:
                return current_user
        
        # 权限不足
        # 安全地获取权限值（处理字符串、枚举和 list）
        perm_values = list(self.required_permissions)
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permissions: {perm_values}",
        )
    
    async def _get_user_permissions(
        self,
        user: User,
    ) -> set[str]:
        """
        获取用户权限（三级缓存策略）
        
        缓存策略：
        1. Session 缓存（优先）：从 current_user.permissions 读取（已在登录时加载）
        2. Redis 缓存（次选）：从 permission_cache 读取
        3. 数据库查询（降级）：从数据库查询并缓存
        
        Args:
            user: 用户对象
            
        Returns:
            set[Permission | str]: 用户权限集合（可以包含枚举和字符串）
        """
        import logging
        logger = logging.getLogger(__name__)
        
        permissions: set[str] = set()
        
        # 超级管理员拥有所有权限
        if user.is_superuser:
            # 添加所有枚举权限
            permissions.update({perm.value for perm in Permission})
            # 添加 "admin" 字符串权限（用于 CRUD 工厂）
            permissions.add("admin")
            # 添加 "*:*:*" 超级权限
            permissions.add(ALL_PERMISSION)
            return permissions
        
        # 🔥 第一级缓存：Session 缓存（优先）
        # 从 current_user.permissions 读取（已在登录时加载到 Session）
        if user.permissions:
            logger.debug(f"从 Session 缓存读取用户权限: user_id={user.id}, permissions={user.permissions}")
            permissions.update(user.permissions)
            
            # 检查是否包含 "*:*:*" 超级权限
            if ALL_PERMISSION in permissions:
                logger.debug(f"用户拥有超级权限 {ALL_PERMISSION}")
            
            return permissions
        
        # 🔥 第二级缓存：Redis 缓存（次选）
        from core.security.permission_cache import permission_cache
        
        user_permissions = await permission_cache.get_permissions(
            user.id, 
            user.tenant_id
        )
        
        if user_permissions is not None:
            logger.debug(f"从 Redis 缓存读取用户权限: user_id={user.id}, permissions={user_permissions}")
            permissions.update(user_permissions)
            
            # 检查是否包含 "*:*:*" 超级权限
            if ALL_PERMISSION in permissions:
                logger.debug(f"用户拥有超级权限 {ALL_PERMISSION}")
            
            return permissions
        
        # 🔥 第三级缓存：数据库查询（降级）
        # 警告：Session 中没有权限信息，可能是旧 Session 或 refresh Session
        logger.warning(
            f"Session 和 Redis 缓存中都没有权限信息，降级查询数据库: "
            f"user_id={user.id}, tenant_id={user.tenant_id}"
        )
        
        # 需要数据库会话，从依赖注入获取
        from core.database import get_async_session
        from services.permission_service import PermissionService
        
        # 🔥 注意：这里需要创建一个新的数据库会话
        # 因为我们已经移除了 db 参数，无法从外部传入
        async for db in get_async_session():
            try:
                permission_service = PermissionService(db)
                user_permissions = await permission_service.get_user_permissions(
                    user.id, 
                    user.tenant_id
                )
                
                # 写入 Redis 缓存
                await permission_cache.set_permissions(
                    user.id,
                    user.tenant_id,
                    user_permissions
                )
                
                logger.info(f"从数据库查询用户权限并缓存: user_id={user.id}, permissions={user_permissions}")
                permissions.update(user_permissions)
                
                # 检查是否包含 "*:*:*" 超级权限
                if ALL_PERMISSION in permissions:
                    logger.debug(f"用户拥有超级权限 {ALL_PERMISSION}")
                
                break
            finally:
                # 确保会话被关闭
                pass
        
        return permissions


# ==================== 便捷函数 ====================

def require_role(*roles: str):
    """
    要求特定角色（满足任一即可）
    
    用法：
        @router.get("/admin/")
        async def admin_page(
            current_user: User = Depends(require_role("admin"))
        ):
            pass
    
    Args:
        *roles: 所需角色列表（字符串）
        
    Returns:
        RoleChecker: 角色检查器实例（可直接用于 Depends）
    """
    return RoleChecker(list(roles))


def require_permissions(*permissions: Permission | str):
    """
    要求特定权限（满足任一即可）
    
    用法：
        @router.get("/users/")
        async def list_users(
            current_user: User = require_permissions(Permission.USER_READ)
        ):
            pass
        
        # 或使用字符串（用于 CRUD 工厂）
        async def list_users(
            current_user: User = require_permissions("admin", "user:read")
        ):
            pass
    
    Args:
        *permissions: 所需权限列表（可以是 Permission 枚举或字符串）
        
    Returns:
        PermissionChecker: 权限检查器实例（可直接用于 Depends）
    """
    return PermissionChecker(list(permissions))


def require_all_permissions(*permissions: Permission | str):
    """
    要求所有权限（必须全部满足）
    
    TODO: 实现需要所有权限的检查器
    
    Args:
        *permissions: 所需权限列表
        
    Returns:
        PermissionChecker: 权限检查器实例
    """
    # 暂时使用 require_permissions，后续可以实现 AllPermissionChecker
    return require_permissions(*permissions)


def require_admin():
    """
    要求管理员角色
    
    Returns:
        Depends: FastAPI 依赖
    """
    return require_role("admin", SUPER_ADMIN_ROLE)


def require_super_admin():
    """
    要求超级管理员角色
    
    Returns:
        Depends: FastAPI 依赖
    """
    return require_role(SUPER_ADMIN_ROLE)


# ==================== 业务逻辑中的权限检查函数 ====================

def check_perms(*permissions: str):
    """
    检查当前用户是否拥有指定权限（OR 逻辑，满足任一即可）
    
    用于在业务逻辑中手动检查权限，不依赖 FastAPI 的依赖注入系统。
    
    用法：
        @router.get("/users/")
        async def list_users(
            current_user: User = Depends(get_current_user)
        ):
            if not check_perms("user:read", "admin")(current_user):
                raise HTTPException(status_code=403, detail="权限不足")
            # 业务逻辑...
    
    Args:
        *permissions: 权限代码列表（字符串）
        
    Returns:
        Callable: 权限检查函数，接受 User 对象，返回 bool
    """
    def check(user: User) -> bool:
        """检查用户是否拥有任一权限"""
        if user.is_superuser:
            return True
        
        user_permissions = set(user.permissions)
        
        # 检查是否拥有 "*:*:*" 超级权限
        if ALL_PERMISSION in user_permissions:
            return True
        
        return any(perm in user_permissions for perm in permissions)
    
    return check


def check_all_perms(*permissions: str):
    """
    检查当前用户是否拥有所有指定权限（AND 逻辑，必须全部满足）
    
    用于在业务逻辑中手动检查权限，不依赖 FastAPI 的依赖注入系统。
    
    用法：
        @router.post("/users/")
        async def create_user(
            current_user: User = Depends(get_current_user)
        ):
            if not check_all_perms("user:create", "user:write")(current_user):
                raise HTTPException(status_code=403, detail="权限不足")
            # 业务逻辑...
    
    Args:
        *permissions: 权限代码列表（字符串）
        
    Returns:
        Callable: 权限检查函数，接受 User 对象，返回 bool
    """
    def check(user: User) -> bool:
        """检查用户是否拥有所有权限"""
        if user.is_superuser:
            return True
        
        user_permissions = set(user.permissions)
        
        # 检查是否拥有 "*:*:*" 超级权限
        if ALL_PERMISSION in user_permissions:
            return True
        
        return all(perm in user_permissions for perm in permissions)
    
    return check


def check_role(*roles: str):
    """
    检查当前用户是否拥有指定角色（OR 逻辑，满足任一即可）
    
    用于在业务逻辑中手动检查角色，不依赖 FastAPI 的依赖注入系统。
    
    用法：
        @router.get("/admin/")
        async def admin_page(
            current_user: User = Depends(get_current_user)
        ):
            if not check_role("admin", SUPER_ADMIN_ROLE)(current_user):
                raise HTTPException(status_code=403, detail="需要管理员角色")
            # 业务逻辑...
    
    Args:
        *roles: 角色代码列表（字符串）
        
    Returns:
        Callable: 角色检查函数，接受 User 对象，返回 bool
    """
    def check(user: User) -> bool:
        """检查用户是否拥有任一角色"""
        if user.is_superuser:
            return True
        
        user_roles = set(user.roles)
        return any(role in user_roles for role in roles)
    
    return check


# ==================== 简化的 Depends 工厂函数 ====================

def has_perms(*permissions: str):
    """
    简化的权限检查（返回 Depends，用于路由装饰器）
    
    用于路由装饰器的 dependencies 参数，提供更简洁的权限声明方式。
    
    用法：
        @router.get("/list", dependencies=[has_perms("role:read", "admin")])
        async def list_roles(...):
            pass
    
    等价于：
        @router.get("/list", dependencies=[Depends(require_permissions("role:read", "admin"))])
        async def list_roles(...):
            pass
    
    Args:
        *permissions: 权限代码列表（字符串）
        
    Returns:
        Depends: FastAPI 依赖
    """
    return Depends(require_permissions(*permissions))


def has_all_perms(*permissions: str):
    """
    要求所有权限（AND 逻辑，返回 Depends）
    
    用于路由装饰器的 dependencies 参数，要求用户拥有所有指定权限。
    
    用法：
        @router.post("/sensitive", dependencies=[has_all_perms("role:write", "role:delete")])
        async def sensitive_operation(...):
            pass
    
    Args:
        *permissions: 权限代码列表（字符串）
        
    Returns:
        Depends: FastAPI 依赖
    """
    return Depends(require_all_permissions(*permissions))


def has_role(*roles: str):
    """
    要求特定角色（返回 Depends）
    
    用于路由装饰器的 dependencies 参数，要求用户拥有特定角色。
    
    用法：
        @router.get("/admin", dependencies=[has_role("admin")])
        async def admin_only(...):
            pass
    
    Args:
        *roles: 角色代码列表（字符串）
        
    Returns:
        Depends: FastAPI 依赖
    """
    return Depends(require_role(*roles))


# ==================== 资源所有权检查 ====================

async def check_resource_ownership(
    resource_owner_id: UUID,
    current_user: User,
    required_permission: Permission | None = None,
) -> bool:
    """
    检查资源所有权
    
    规则：
    1. 资源所有者可以访问
    2. 超级管理员可以访问
    3. 有特定权限的用户可以访问
    
    Args:
        resource_owner_id: 资源所有者 ID
        current_user: 当前用户
        required_permission: 所需权限（可选）
        
    Returns:
        bool: 是否有权限
    """
    # 1. 资源所有者
    if resource_owner_id == current_user.id:
        return True
    
    # 2. 超级管理员
    if current_user.is_superuser:
        return True
    
    # 3. 检查特定权限
    if required_permission:
        # TODO: 从数据库查询用户权限
        pass
    
    return False


async def require_resource_ownership(
    resource_owner_id: UUID,
    current_user: User = Depends(get_current_user),
) -> User:
    """
    要求资源所有权（用作依赖）
    
    Args:
        resource_owner_id: 资源所有者 ID
        current_user: 当前用户
        
    Returns:
        User: 当前用户
        
    Raises:
        HTTPException: 权限不足
    """
    if not await check_resource_ownership(resource_owner_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this resource",
        )
    
    return current_user
