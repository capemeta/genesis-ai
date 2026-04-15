"""
常量定义
"""
from enum import Enum


# ==================== 用户状态 ====================

class UserStatus(str, Enum):
    """用户状态枚举"""
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"


# ==================== 可见性 ====================

class Visibility(str, Enum):
    """资源可见性枚举"""
    PRIVATE = "private"
    TENANT_PUBLIC = "tenant_public"


# ==================== 权限类型 ====================

class PermissionType(str, Enum):
    """权限类型枚举"""
    VIEW = "view"
    EDIT = "edit"
    MANAGE = "manage"
    DELETE = "delete"


# ==================== 资源类型 ====================

class ResourceType(str, Enum):
    """资源类型枚举"""
    KNOWLEDGE_BASE = "knowledge_base"
    DOCUMENT = "document"
    FOLDER = "folder"
    SEGMENT = "segment"


# ==================== 主体类型 ====================

class SubjectType(str, Enum):
    """权限主体类型枚举"""
    USER = "user"
    ROLE = "role"
    ORGANIZATION = "organization"


# ==================== 角色常量 ====================

# 超级管理员角色代码
SUPER_ADMIN_ROLE = "super_admin"


# ==================== 权限常量 ====================

# 所有权限标识（超级管理员拥有所有功能权限）
ALL_PERMISSION = "*:*:*"


# ==================== 文档状态 ====================

class DocumentStatus(str, Enum):
    """文档状态枚举"""
    UPLOADING = "uploading"
    PARSING = "parsing"
    SUCCESS = "success"
    ERROR = "error"


# ==================== 存储驱动 ====================

class StorageDriver(str, Enum):
    """存储驱动枚举"""
    LOCAL = "local"
    S3 = "s3"
    SEAWEEDFS = "seaweedfs"


# ==================== 错误码 ====================

class ErrorCode(str, Enum):
    """错误码枚举"""
    # 认证相关
    INVALID_CREDENTIALS = "AUTH_001"
    TOKEN_EXPIRED = "AUTH_002"
    INVALID_TOKEN = "AUTH_003"
    USER_NOT_FOUND = "AUTH_004"
    USER_ALREADY_EXISTS = "AUTH_005"
    
    # 权限相关
    PERMISSION_DENIED = "PERM_001"
    TENANT_NOT_FOUND = "PERM_002"
    
    # 资源相关
    RESOURCE_NOT_FOUND = "RES_001"
    RESOURCE_CONFLICT = "RES_002"
    
    # 验证相关
    VALIDATION_ERROR = "VAL_001"
    
    # 服务器相关
    INTERNAL_ERROR = "SRV_001"
