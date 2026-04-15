"""
创建初始租户和管理员用户
在首次启动应用前运行此脚本
"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from core.database.session import engine as async_engine, async_session_maker as AsyncSessionLocal
from core.security import get_password_hash
from models.tenant import Tenant
from models.user import User


# 默认租户和管理员 ID
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_ADMIN_ID = UUID("00000000-0000-0000-0000-000000000001")


async def create_initial_data():
    """创建初始租户和管理员用户"""
    
    async with AsyncSessionLocal() as session:
        # 检查租户是否已存在
        result = await session.execute(
            select(Tenant).where(Tenant.id == DEFAULT_TENANT_ID)
        )
        existing_tenant = result.scalar_one_or_none()
        
        if existing_tenant:
            print(f"✅ 租户已存在: {existing_tenant.name}")
        else:
            # 创建默认租户
            tenant = Tenant(
                id=DEFAULT_TENANT_ID,
                owner_id=DEFAULT_ADMIN_ID,
                name="Default Tenant",
                description="Default tenant for initial setup",
            )
            session.add(tenant)
            await session.flush()
            print(f"✅ 创建租户: {tenant.name}")
        
        # 检查管理员是否已存在
        result = await session.execute(
            select(User).where(User.id == DEFAULT_ADMIN_ID)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"✅ 管理员已存在: {existing_user.username}")
        else:
            # 创建管理员用户
            admin_password = "admin123"  # 默认密码，生产环境请修改
            admin = User(
                id=DEFAULT_ADMIN_ID,
                tenant_id=DEFAULT_TENANT_ID,
                username="admin",
                nickname="Administrator",
                password_hash=get_password_hash(admin_password),
                email="admin@example.com",
                status="active",
            )
            session.add(admin)
            await session.flush()
            print(f"✅ 创建管理员: {admin.username}")
            print(f"   默认密码: {admin_password}")
            print(f"   ⚠️  请在生产环境中修改密码！")
        
        # 提交事务
        await session.commit()
        print("\n✅ 初始数据创建完成！")
        print("\n📝 登录信息：")
        print(f"   用户名: admin")
        print(f"   密码: admin123")
        print(f"   租户ID: {DEFAULT_TENANT_ID}")


async def main():
    """主函数"""
    print("=" * 60)
    print("创建初始租户和管理员用户")
    print("=" * 60)
    print()
    
    try:
        # 创建数据库表（如果不存在）
        from models.base import Base
        async with async_engine.begin() as conn:
            # 注意：这只会创建 SQLAlchemy 模型定义的表
            # 完整的表结构应该通过 docker/postgresql/init-schema.sql 创建
            await conn.run_sync(Base.metadata.create_all)
        
        # 创建初始数据
        await create_initial_data()
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # 关闭数据库连接
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
