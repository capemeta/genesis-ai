"""
安全模块
"""
from core.security.auth import (
    security,
    get_current_user,
    get_current_active_user,
    get_current_superuser,
    authenticate_user,
    update_last_login,
    get_session_service,
)
from core.security.password import PasswordValidator
from core.security.captcha import CaptchaGenerator, CaptchaService, get_captcha_service
from core.security.rate_limiter import RateLimiter, get_rate_limiter
from core.security.permissions import (
    Permission,
    PermissionChecker,
    require_permissions,
    require_all_permissions,
    require_admin,
    require_super_admin,
    check_resource_ownership,
    require_resource_ownership,
    # 新的简化权限注解函数
    has_perms,
    has_all_perms,
    has_role,
    check_perms,
    check_all_perms,
    check_role,
)
from core.security.crypto import (
    verify_password,
    get_password_hash,
)

__all__ = [
    # Auth
    "security",
    "get_current_user",
    "get_current_active_user",
    "get_current_superuser",
    "authenticate_user",
    "update_last_login",
    "get_session_service",
    # Password
    "PasswordValidator",
    # Captcha
    "CaptchaGenerator",
    "CaptchaService",
    "get_captcha_service",
    # Rate Limiter
    "RateLimiter",
    "get_rate_limiter",
    # Permissions
    "Permission",
    "PermissionChecker",
    "require_permissions",
    "require_all_permissions",
    "require_admin",
    "require_super_admin",
    "check_resource_ownership",
    "require_resource_ownership",
    # 新的简化权限注解函数
    "has_perms",
    "has_all_perms",
    "has_role",
    "check_perms",
    "check_all_perms",
    "check_role",
    # Crypto
    "verify_password",
    "get_password_hash",
]
