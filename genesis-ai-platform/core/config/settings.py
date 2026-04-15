"""
应用配置管理
使用 Pydantic Settings 管理所有配置项
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import Any


class Settings(BaseSettings):
    """应用配置类"""
    
    # ==================== 应用配置 ====================
    APP_NAME: str = "Genesis AI Platform"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    PORT: int = 8200  # 服务端口
    ROOT_PATH: str = "/"  # 应用根路径上下文
    API_V1_PREFIX: str = "/api/v1"  # API 路由前缀（相对于 ROOT_PATH）
    # 对外公开资源访问基地址（用于生成 markdown 中的绝对图片链接）
    # 例如: http://localhost:8200/genesis-ai
    PUBLIC_API_BASE_URL: str | None = None
    
    # ==================== 数据库配置 ====================
    # 方式1：直接使用完整的 DATABASE_URL（优先级最高）
    DATABASE_URL: str | None = None
    
    # 方式2：使用拆分的配置项（当 DATABASE_URL 为空时使用，必须在 .env 中配置）
    DB_HOST: str | None = None
    DB_PORT: int = 5432
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    DB_NAME: str | None = None
    DB_DRIVER: str = "postgresql+asyncpg"
    
    # 连接池配置：FastAPI + 5 个 Celery 进程共 6 个进程，每进程独立池子，总连接数 = 6 * (pool_size + max_overflow)
    # PostgreSQL 默认 max_connections≈100，故单进程不宜过大；可在 .env 中按需调大
    DB_ECHO: bool = True  # 🔥 启用 SQL 日志输出
    DB_POOL_SIZE: int = 5  # 基础连接池大小
    DB_MAX_OVERFLOW: int = 5  # 溢出连接数（单进程最多 pool_size + max_overflow）
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600  # 连接回收时间（秒），减少僵死连接
    
    def get_database_url(self) -> str:
        """
        获取数据库连接 URL
        优先使用 DATABASE_URL，如果为空则从拆分的配置项构建
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        
        # 从拆分的配置项构建 URL
        if not all([self.DB_HOST, self.DB_USER, self.DB_PASSWORD, self.DB_NAME]):
            raise ValueError(
                "Database configuration incomplete. "
                "Either set DATABASE_URL or all of (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)"
            )
        
        # 自动处理密码中的特殊字符
        from urllib.parse import quote_plus
        password = quote_plus(str(self.DB_PASSWORD))
        return f"{self.DB_DRIVER}://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # ==================== Redis 配置 ====================
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_DB: int = 0
    REDIS_SESSION_DB: int = 1
    REDIS_CELERY_BROKER_DB: int = 2
    REDIS_CELERY_RESULT_DB: int = 3
    
    # ==================== Celery 配置 ====================
    CELERY_BROKER_URL: str = "redis://localhost:6379/2"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/3"
    CELERY_TASK_SERIALIZER: str = "msgpack"
    CELERY_RESULT_SERIALIZER: str = "msgpack"
    CELERY_TIMEZONE: str = "Asia/Shanghai"
    
    # ==================== WebSync 清理任务配置 ====================
    WEB_SYNC_CLEANUP_ENABLED: bool = True
    WEB_SYNC_CLEANUP_CRON_HOUR: int = 5
    WEB_SYNC_CLEANUP_CRON_MINUTE: int = 30
    WEB_SYNC_CLEANUP_MAX_VERSIONS_PER_PAGE: int = 20
    WEB_SYNC_CLEANUP_RETENTION_DAYS: int = 180
    WEB_SYNC_CLEANUP_PAGE_BATCH_SIZE: int = 1000
    
    # ==================== 安全配置 ====================
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    
    # Token 过期时间（不记住我）
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30分钟
    REFRESH_TOKEN_EXPIRE_DAYS: int = 3  # 3天
    
    # Token 过期时间（记住我）
    ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER: int = 120  # 2小时
    REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER: int = 30  # 30天
    
    # Token 存储策略
    TOKEN_STORAGE: str = "redis"  # redis 或 jwt（无状态）
    ENABLE_SINGLE_DEVICE_LOGIN: bool = False  # 是否启用单设备登录
    
    @property
    def validated_secret_key(self) -> str:
        """验证并返回 SECRET_KEY"""
        if self.SECRET_KEY == "your-secret-key-change-in-production":
            raise ValueError(
                "SECRET_KEY 必须在环境变量中设置！\n"
                "生成方法: python -c \"import secrets; print(secrets.token_hex(32))\"\n"
                "或: openssl rand -hex 32"
            )
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY 长度必须至少 32 个字符")
        return self.SECRET_KEY
    
    # ==================== CORS 配置 ====================
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]
    
    @property
    def cors_origins_list(self) -> list[str]:
        """
        获取 CORS 允许的源列表
        支持从环境变量读取逗号分隔的字符串
        """
        if isinstance(self.CORS_ORIGINS, str):
            # 如果是字符串，按逗号分割
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return self.CORS_ORIGINS
    
    # ==================== 存储配置 ====================
    STORAGE_DRIVER: str = "local"  # local, s3, seaweedfs
    LOCAL_STORAGE_PATH: str = "./storage-data"
    
    # SeaweedFS/S3 配置
    SEAWEEDFS_ENDPOINT: str | None = None
    SEAWEEDFS_ACCESS_KEY: str | None = None
    SEAWEEDFS_SECRET_KEY: str | None = None
    SEAWEEDFS_BUCKET: str = "genesis-ai-files"
    SEAWEEDFS_REGION: str = "us-east-1"
    
    # SeaweedFS/S3 管理员凭证（可选，用于自动创建 bucket）
    SEAWEEDFS_ADMIN_ACCESS_KEY: str | None = None
    SEAWEEDFS_ADMIN_SECRET_KEY: str | None = None
    
    # ==================== LLM 配置 ====================
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE: str | None = None

    # ==================== 检索后端默认配置 ====================
    # 当前项目默认使用 PostgreSQL 本地实现，未来可通过 .env 切换到外部后端。
    DEFAULT_VECTOR_SEARCH_BACKEND: str = "pg_vector"
    DEFAULT_LEXICAL_SEARCH_BACKEND: str = "pg_fts"
    
    # ==================== 文件上传配置 ====================
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_MIME_TYPES: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/markdown",
        "text/csv",
    ]
    
    # ==================== RAG 分块流程并发控制配置 ====================
    # 解析任务并发限制（CPU 密集）
    RAG_PARSE_CONCURRENCY: int = 4

    # 解析任务超时（秒）
    # 对 PDF 尤其是 MinerU / OCR 类任务，需要显著长于普通文本解析。
    RAG_PARSE_TASK_SOFT_TIME_LIMIT: int = 3600
    RAG_PARSE_TASK_TIME_LIMIT: int = 3660
    
    # 分块任务并发限制（CPU 轻量）
    RAG_CHUNK_CONCURRENCY: int = 2
    
    # 向量化任务并发限制（I/O 密集，调用 Embedding API）
    RAG_EMBED_CONCURRENCY: int = 50
    RAG_EMBED_CACHE_ENABLED: bool = True
    RAG_EMBED_CACHE_TTL_SECONDS: int = 21600
    RAG_EMBED_CACHE_MAX_ITEMS: int = 2000
    RAG_EMBED_CACHE_MAX_TEXT_LENGTH: int = 4000
    
    # LLM 调用任务并发限制（I/O 密集 + API 限流）
    RAG_LLM_CONCURRENCY: int = 10
    RAG_LLM_CONCURRENCY_MODE: str = "wait"
    RAG_LLM_CONCURRENCY_WAIT_TIMEOUT_SECONDS: int = 300
    
    # 知识图谱任务并发限制（I/O 密集）
    RAG_KG_CONCURRENCY: int = 2
    
    # MinIO 上传任务并发限制（I/O 密集）
    RAG_MINIO_CONCURRENCY: int = 20
    
    # 并发租约基础配置
    RAG_CONCURRENCY_LEASE_TTL_SECONDS: int = 600
    RAG_CONCURRENCY_POLL_INTERVAL_MS: int = 200
    
    # ==================== RAG 安全检查配置 ====================
    # 分块安全检查模式：A (混合单位), B (Tiktoken 工业标准)
    RAG_CHUNK_SAFE_CHECK_SCHEMA: str = "B"
    
    # ==================== 日志配置 ====================
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"  # json or text
    LOG_DIR_ROOT: str = "./logs"
    LOG_FILE_WHEN: str = "midnight"
    LOG_FILE_INTERVAL: int = 1
    LOG_FILE_BACKUP_COUNT: int = 14

    # ==================== MinerU 配置 ====================
    # 连接超时保持较短，读取超时需要允许长任务。
    MINERU_CONNECT_TIMEOUT: int = 30
    MINERU_READ_TIMEOUT: int = 3600
    MINERU_TIMEOUT: int = 3600

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def validate_environment(cls, v: Any) -> str:
        """
        规范化运行环境名称

        说明：
        - 将常见别名统一映射为 development / testing / staging / production
        - 便于后续根据环境做默认行为控制，但不强制要求必须配置该字段
        """
        if v is None or v == "":
            return "development"

        normalized = str(v).strip().lower()
        alias_map = {
            "dev": "development",
            "development": "development",
            "local": "development",
            "test": "testing",
            "testing": "testing",
            "stage": "staging",
            "staging": "staging",
            "prod": "production",
            "production": "production",
            "release": "production",
        }
        return alias_map.get(normalized, normalized)

    @field_validator("DEBUG", mode="before")
    @classmethod
    def validate_debug(cls, v: Any) -> bool:
        """
        兼容多种 DEBUG 配置写法

        历史上部分环境会误写成：
        - DEBUG=release
        - DEBUG=prod
        - DEBUG=development

        这里做兼容映射，避免启动阶段直接因布尔解析失败中断。
        """
        if isinstance(v, bool):
            return v
        if v is None or v == "":
            return False

        normalized = str(v).strip().lower()

        truthy_values = {"1", "true", "yes", "on", "debug", "dev", "development", "local"}
        falsy_values = {"0", "false", "no", "off", "release", "prod", "production", "staging"}

        if normalized in truthy_values:
            return True
        if normalized in falsy_values:
            return False

        raise ValueError("DEBUG 必须是布尔值或可识别的环境别名（如 true/false/dev/release）")

    @field_validator("DEFAULT_VECTOR_SEARCH_BACKEND")
    @classmethod
    def validate_default_vector_search_backend(cls, v: str) -> str:
        """校验默认向量检索后端。"""
        valid_values = {"pg_vector", "qdrant", "milvus"}
        if v not in valid_values:
            raise ValueError(f"DEFAULT_VECTOR_SEARCH_BACKEND 必须是以下之一: {', '.join(sorted(valid_values))}")
        return v

    @field_validator("DEFAULT_LEXICAL_SEARCH_BACKEND")
    @classmethod
    def validate_default_lexical_search_backend(cls, v: str) -> str:
        """校验默认全文检索后端。"""
        valid_values = {"pg_fts", "qdrant", "milvus"}
        if v not in valid_values:
            raise ValueError(f"DEFAULT_LEXICAL_SEARCH_BACKEND 必须是以下之一: {', '.join(sorted(valid_values))}")
        return v

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def validate_log_level(cls, v: Any) -> str:
        """统一日志级别写法，避免大小写不一致。"""
        normalized = str(v or "INFO").strip().upper()
        valid_values = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if normalized not in valid_values:
            raise ValueError(f"LOG_LEVEL 必须是以下之一: {', '.join(sorted(valid_values))}")
        return normalized

    @field_validator("LOG_FORMAT", mode="before")
    @classmethod
    def validate_log_format(cls, v: Any) -> str:
        """校验日志输出格式。"""
        normalized = str(v or "text").strip().lower()
        valid_values = {"json", "text"}
        if normalized not in valid_values:
            raise ValueError(f"LOG_FORMAT 必须是以下之一: {', '.join(sorted(valid_values))}")
        return normalized

    @field_validator("LOG_FILE_WHEN", mode="before")
    @classmethod
    def validate_log_file_when(cls, v: Any) -> str:
        """校验文件轮转周期配置。"""
        normalized = str(v or "midnight").strip().lower()
        valid_values = {"s", "m", "h", "d", "w0", "w1", "w2", "w3", "w4", "w5", "w6", "midnight"}
        if normalized not in valid_values:
            raise ValueError(
                f"LOG_FILE_WHEN 必须是以下之一: {', '.join(sorted(valid_values))}"
            )
        return normalized
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # 忽略额外的环境变量字段


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 导出配置实例
settings = get_settings()
