"""
配置验证器
启动时检查关键配置项
"""
import sys
import secrets
from pathlib import Path

# 添加项目根目录到路径
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.config.settings import settings


class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_secret_key():
        """验证 SECRET_KEY"""
        # 检查是否使用默认值
        if settings.SECRET_KEY == "your-secret-key-change-in-production":
            print("SECURITY ERROR: SECRET_KEY is using default value!")
            print("   Please set a strong random SECRET_KEY in your .env file")
            print("   You can generate one using: python -c 'import secrets; print(secrets.token_urlsafe(32))'")
            sys.exit(1)
        
        # 检查长度
        if len(settings.SECRET_KEY) < 32:
            print("WARNING: SECRET_KEY is too short (< 32 characters)")
            print("   Consider using a longer key for better security")
    
    @staticmethod
    def validate_database_url():
        """验证数据库 URL"""
        db_url = settings.get_database_url()
        if not db_url:
            print("ERROR: Database configuration is not set")
            sys.exit(1)
        
        # 生产环境检查
        if not settings.DEBUG:
            if "localhost" in db_url or "127.0.0.1" in db_url:
                print("WARNING: Using localhost database in production mode")
    
    @staticmethod
    def validate_cors_origins():
        """验证 CORS 配置"""
        if not settings.DEBUG:
            # 生产环境不应该允许所有来源
            if "*" in settings.CORS_ORIGINS:
                print("SECURITY ERROR: CORS allows all origins in production!")
                print("   Please specify exact origins in CORS_ORIGINS")
                sys.exit(1)
    
    @staticmethod
    def validate_token_expiry():
        """验证 Token 过期时间"""
        # Access Token 不应该太长
        if settings.ACCESS_TOKEN_EXPIRE_MINUTES > 1440:  # 24小时
            print("WARNING: ACCESS_TOKEN_EXPIRE_MINUTES is very long (> 24 hours)")
            print("   Consider using shorter expiry time with refresh tokens")
        
        # Refresh Token 不应该太短
        if settings.REFRESH_TOKEN_EXPIRE_DAYS < 1:
            print("WARNING: REFRESH_TOKEN_EXPIRE_DAYS is too short (< 1 day)")
    
    @staticmethod
    def validate_all():
        """验证所有配置"""
        print("[VALIDATING] Validating configuration...")
        
        ConfigValidator.validate_secret_key()
        ConfigValidator.validate_database_url()
        ConfigValidator.validate_cors_origins()
        ConfigValidator.validate_token_expiry()
        
        print("[PASSED] Configuration validation passed")
    
    @staticmethod
    def generate_secret_key() -> str:
        """生成安全的 SECRET_KEY"""
        return secrets.token_urlsafe(32)


if __name__ == "__main__":
    # 生成新的 SECRET_KEY
    print("Generated SECRET_KEY:")
    print(ConfigValidator.generate_secret_key())
