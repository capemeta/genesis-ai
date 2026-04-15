"""
应用生命周期管理
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from core.database.session import init_db, close_db, async_session_maker

logger = logging.getLogger(__name__)


async def init_storage():
    """
    初始化存储系统
    
    检查并创建必要的 S3 bucket
    """
    from core.config import settings
    
    # 只在使用 S3 存储时初始化
    if settings.STORAGE_DRIVER != "s3":
        logger.info(f"Storage driver: {settings.STORAGE_DRIVER}, skip S3 initialization")
        return
    
    try:
        import aioboto3
        from botocore.exceptions import ClientError
        
        # 优先使用管理员凭证创建 bucket（如果配置了）
        # 否则使用普通凭证尝试
        admin_access_key = getattr(settings, "SEAWEEDFS_ADMIN_ACCESS_KEY", None)
        admin_secret_key = getattr(settings, "SEAWEEDFS_ADMIN_SECRET_KEY", None)
        
        if admin_access_key and admin_secret_key:
            access_key = admin_access_key
            secret_key = admin_secret_key
            logger.info("Using admin credentials for S3 initialization")
        else:
            access_key = settings.SEAWEEDFS_ACCESS_KEY
            secret_key = settings.SEAWEEDFS_SECRET_KEY
            logger.info("Using regular credentials for S3 initialization")
        
        session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=settings.SEAWEEDFS_REGION
        )
        
        async with session.client(
            's3',
            endpoint_url=settings.SEAWEEDFS_ENDPOINT,
            region_name=settings.SEAWEEDFS_REGION
        ) as s3:
            bucket = settings.SEAWEEDFS_BUCKET
            
            # 检查 bucket 是否存在
            try:
                await s3.head_bucket(Bucket=bucket)
                logger.info(f"✅ S3 bucket '{bucket}' already exists")
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    # Bucket 不存在，尝试创建
                    logger.info(f"S3 bucket '{bucket}' not found, creating...")
                    try:
                        await s3.create_bucket(Bucket=bucket)
                        logger.info(f"✅ S3 bucket '{bucket}' created successfully")
                    except ClientError as create_error:
                        logger.error(f"❌ Failed to create S3 bucket '{bucket}': {create_error}")
                        logger.error("Please create the bucket manually or configure admin credentials")
                        raise
                else:
                    logger.error(f"❌ Failed to check S3 bucket '{bucket}': {e}")
                    raise
        
        logger.info("✅ Storage initialized")
        
    except ImportError:
        logger.warning("aioboto3 not installed, skip S3 initialization")
    except Exception as e:
        logger.error(f"❌ Storage initialization failed: {e}")
        # 不阻止应用启动，但记录错误
        logger.warning("Application will start but file upload may not work")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    启动时：
    - 初始化数据库连接
    - 创建数据库表（开发环境）
    - 初始化存储系统（检查/创建 S3 bucket）
    
    关闭时：
    - 关闭数据库连接
    """
    # 启动时初始化
    print("🚀 Starting Genesis AI Platform...")
    
    # 初始化数据库（开发环境自动创建表）
    # 生产环境应使用 Alembic 迁移
    await init_db()
    print("✅ Database initialized")

    # 初始化内置模型厂商定义，避免首次启动时管理页为空
    try:
        from services.model_platform_service import seed_builtin_model_provider_definitions

        async with async_session_maker() as session:
            seeded_count = await seed_builtin_model_provider_definitions(session)
            if seeded_count > 0:
                logger.info("✅ Seeded builtin model provider definitions: %s", seeded_count)
    except Exception as e:
        logger.warning("初始化内置模型厂商定义失败: %s", e)

    # 初始化存储系统
    await init_storage()

    print("✅ Storage initialized")

    yield
    
    # 关闭时清理
    print("🛑 Shutting down Genesis AI Platform...")
    await close_db()
    print("✅ Database connections closed")
