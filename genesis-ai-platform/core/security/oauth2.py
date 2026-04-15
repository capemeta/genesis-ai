"""
OAuth 2.0 支持
为未来的 OAuth 2.0 集成预留接口
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel
from enum import Enum


class GrantType(str, Enum):
    """OAuth 2.0 授权类型"""
    PASSWORD = "password"  # 密码模式（当前使用）
    AUTHORIZATION_CODE = "authorization_code"  # 授权码模式
    CLIENT_CREDENTIALS = "client_credentials"  # 客户端凭证模式
    REFRESH_TOKEN = "refresh_token"  # 刷新令牌
    IMPLICIT = "implicit"  # 隐式模式（不推荐）


class TokenRequest(BaseModel):
    """OAuth 2.0 Token 请求"""
    grant_type: GrantType
    
    # Password Grant
    username: Optional[str] = None
    password: Optional[str] = None
    
    # Authorization Code Grant
    code: Optional[str] = None
    redirect_uri: Optional[str] = None
    code_verifier: Optional[str] = None  # PKCE
    
    # Client Credentials Grant
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    
    # Refresh Token Grant
    refresh_token: Optional[str] = None
    
    # Common
    scope: Optional[str] = None


class TokenResponse(BaseModel):
    """OAuth 2.0 Token 响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    
    # OpenID Connect 扩展
    id_token: Optional[str] = None


class OAuth2Client(BaseModel):
    """OAuth 2.0 客户端"""
    client_id: str
    client_secret: str
    client_name: str
    redirect_uris: List[str]
    grant_types: List[GrantType]
    scope: List[str]
    tenant_id: UUID


class AuthorizationCode(BaseModel):
    """授权码"""
    code: str
    client_id: str
    redirect_uri: str
    user_id: UUID
    tenant_id: UUID
    scope: List[str]
    expires_at: int
    
    # PKCE 支持
    code_challenge: Optional[str] = None
    code_challenge_method: Optional[str] = None


class Scope:
    """标准 OAuth 2.0 Scope"""
    # 基础权限
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    
    # 用户权限
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    
    # 知识库权限
    KB_READ = "kb:read"
    KB_WRITE = "kb:write"
    KB_DELETE = "kb:delete"
    
    # 文档权限
    DOC_READ = "doc:read"
    DOC_WRITE = "doc:write"
    DOC_DELETE = "doc:delete"
    
    # 管理员权限
    ADMIN = "admin"
    
    # OpenID Connect
    OPENID = "openid"
    PROFILE = "profile"
    EMAIL = "email"
    
    @classmethod
    def parse_scope_string(cls, scope_string: str) -> List[str]:
        """解析 scope 字符串"""
        if not scope_string:
            return []
        return [s.strip() for s in scope_string.split() if s.strip()]
    
    @classmethod
    def validate_scope(cls, requested_scope: List[str], allowed_scope: List[str]) -> bool:
        """验证请求的 scope 是否在允许范围内"""
        return all(s in allowed_scope for s in requested_scope)


class OAuth2Service:
    """
    OAuth 2.0 服务
    
    未来扩展：
    1. 授权码模式（Authorization Code）
    2. 客户端凭证模式（Client Credentials）
    3. PKCE 支持
    4. OpenID Connect 支持
    """
    
    def __init__(self, token_service, client_repository=None):
        self.token_service = token_service
        self.client_repository = client_repository
    
    async def handle_password_grant(
        self,
        username: str,
        password: str,
        scope: Optional[List[str]],
        user_service,
    ) -> TokenResponse:
        """
        处理密码模式（当前使用）
        
        Args:
            username: 用户名
            password: 密码
            scope: 请求的权限范围
            user_service: 用户服务
        
        Returns:
            Token 响应
        """
        # 验证用户
        user = await user_service.authenticate(username, password)
        if not user:
            raise ValueError("Invalid credentials")
        
        # 创建 token
        token_data = await self.token_service.create_token_pair(
            user_id=user.id,
            tenant_id=user.tenant_id,
            client_ip="",  # 从请求中获取
            scope=scope,
        )
        
        return TokenResponse(**token_data)
    
    async def handle_refresh_token_grant(
        self,
        refresh_token: str,
        scope: Optional[List[str]],
    ) -> TokenResponse:
        """
        处理刷新令牌模式
        
        Args:
            refresh_token: 刷新令牌
            scope: 请求的权限范围
        
        Returns:
            Token 响应
        """
        token_data = await self.token_service.refresh_token(
            refresh_token=refresh_token,
            client_ip="",  # 从请求中获取
        )
        
        return TokenResponse(**token_data)
    
    async def handle_authorization_code_grant(
        self,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: Optional[str],
        code_verifier: Optional[str],
    ) -> TokenResponse:
        """
        处理授权码模式（未来实现）
        
        Args:
            code: 授权码
            redirect_uri: 重定向 URI
            client_id: 客户端 ID
            client_secret: 客户端密钥
            code_verifier: PKCE 验证码
        
        Returns:
            Token 响应
        """
        raise NotImplementedError("Authorization Code Grant not implemented yet")
    
    async def handle_client_credentials_grant(
        self,
        client_id: str,
        client_secret: str,
        scope: Optional[List[str]],
    ) -> TokenResponse:
        """
        处理客户端凭证模式（未来实现）
        
        用于服务间调用（Machine-to-Machine）
        
        Args:
            client_id: 客户端 ID
            client_secret: 客户端密钥
            scope: 请求的权限范围
        
        Returns:
            Token 响应
        """
        raise NotImplementedError("Client Credentials Grant not implemented yet")
    
    def validate_scope(self, requested_scope: List[str], user_permissions: List[str]) -> List[str]:
        """
        验证并过滤 scope
        
        Args:
            requested_scope: 请求的 scope
            user_permissions: 用户拥有的权限
        
        Returns:
            有效的 scope 列表
        """
        if not requested_scope:
            return user_permissions
        
        # 只返回用户拥有的权限
        return [s for s in requested_scope if s in user_permissions]


# 未来扩展：OpenID Connect 支持
class OpenIDConnectService:
    """
    OpenID Connect 服务
    
    未来实现：
    1. ID Token 生成
    2. UserInfo 端点
    3. Discovery 端点
    4. JWKS 端点
    """
    
    def create_id_token(
        self,
        user_id: UUID,
        client_id: str,
        nonce: Optional[str] = None,
    ) -> str:
        """
        创建 ID Token（未来实现）
        
        Args:
            user_id: 用户 ID
            client_id: 客户端 ID
            nonce: 随机数
        
        Returns:
            ID Token（JWT）
        """
        raise NotImplementedError("OpenID Connect not implemented yet")
