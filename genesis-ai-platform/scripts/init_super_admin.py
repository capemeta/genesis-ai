"""
初始化超级管理员脚本（改进版）

特点：
1. 使用随机生成的 UUID
2. 可自定义管理员用户名和密码
3. 输出初始化信息到文件（便于保存）
4. 支持环境变量配置

使用方法：
    # 使用默认配置
    uv run python scripts/init_super_admin.py
    
    # 自定义配置
    uv run python scripts/init_super_admin.py --username admin --password "YourSecurePassword@123"
    
    # 从环境变量读取
    export ADMIN_USERNAME=admin
    export ADMIN_PASSWORD="YourSecurePassword@123"
    uv run python scripts/init_super_admin.py
"""
import asyncio
import argparse
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

from models.tenant import Tenant
from models.user import User
from models.role import Role
from models.permission import Permission
from core.config import settings


# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def init_super_admin(
    username: str = "admin",
    password: str = "Admin@123456",
    email: str = "admin@genesis-ai.com",
    tenant_name: str = "Default Tenant"
):
    """
    初始化超级管理员
    
    Args:
        username: 管理员用户名
        password: 管理员密码
        email: 管理员邮箱
        tenant_name: 租户名称
    """
    # 创建数据库引擎
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # 1. 检查是否已存在默认租户
            result = await session.execute(
                select(Tenant).where(Tenant.name == tenant_name)
            )
            tenant = result.scalar_one_or_none()
            
            if tenant:
                print(f"✓ 默认租户已存在: {tenant.name} (ID: {tenant.id})")
                tenant_id = tenant.id
            else:
                # 创建新租户
                tenant_id = uuid4()
                tenant = Tenant(
                    id=tenant_id,
                    owner_id=tenant_id,  # 临时使用租户 ID，后面会更新
                    name=tenant_name,
                    description="系统默认租户",
                    limits={
                        "max_users": 1000,
                        "max_storage_gb": 10000,
                        "max_knowledge_bases": 100
                    },
                    created_by_id=tenant_id,
                    created_by_name="System",
                    updated_by_id=tenant_id,
                    updated_by_name="System"
                )
                session.add(tenant)
                await session.flush()
                print(f"✓ 创建默认租户: {tenant.name} (ID: {tenant.id})")
            
            # 2. 检查是否已存在管理员用户
            result = await session.execute(
                select(User).where(
                    User.username == username,
                    User.tenant_id == tenant_id
                )
            )
            admin_user = result.scalar_one_or_none()
            
            if admin_user:
                print(f"✓ 管理员用户已存在: {admin_user.username} (ID: {admin_user.id})")
                admin_id = admin_user.id
                
                # 更新密码（如果提供了新密码）
                if password != "Admin@123456":
                    admin_user.password_hash = pwd_context.hash(password)
                    print(f"✓ 更新管理员密码")
            else:
                # 创建新管理员
                admin_id = uuid4()
                admin_user = User(
                    id=admin_id,
                    tenant_id=tenant_id,
                    username=username,
                    nickname="超级管理员",
                    password_hash=pwd_context.hash(password),
                    email=email,
                    status="active",
                    created_by_id=admin_id,
                    created_by_name="System",
                    updated_by_id=admin_id,
                    updated_by_name="System"
                )
                session.add(admin_user)
                await session.flush()
                print(f"✓ 创建管理员用户: {admin_user.username} (ID: {admin_user.id})")
                
                # 更新租户的 owner_id
                tenant.owner_id = admin_id
                tenant.updated_by_id = admin_id
                tenant.updated_at = datetime.now(timezone.utc)
            
            # 3. 创建超级管理员角色
            result = await session.execute(
                select(Role).where(
                    Role.tenant_id == tenant_id,
                    Role.name == "Super Admin"
                )
            )
            role = result.scalar_one_or_none()
            
            if not role:
                role_id = uuid4()
                role = Role(
                    id=role_id,
                    tenant_id=tenant_id,
                    name="Super Admin",
                    description="超级管理员角色，拥有所有权限",
                    is_system=True,
                    created_by_id=admin_id,
                    created_by_name="超级管理员",
                    updated_by_id=admin_id,
                    updated_by_name="超级管理员"
                )
                session.add(role)
                await session.flush()
                print(f"✓ 创建超级管理员角色 (ID: {role.id})")
            else:
                print(f"✓ 超级管理员角色已存在 (ID: {role.id})")
            
            # 4. 关联用户和角色
            result = await session.execute(
                text("""
                    SELECT 1 FROM user_roles 
                    WHERE user_id = :user_id AND role_id = :role_id
                """),
                {"user_id": admin_id, "role_id": role.id}
            )
            if not result.scalar_one_or_none():
                await session.execute(
                    text("""
                        INSERT INTO user_roles (user_id, role_id, tenant_id, created_at)
                        VALUES (:user_id, :role_id, :tenant_id, :created_at)
                    """),
                    {
                        "user_id": admin_id,
                        "role_id": role.id,
                        "tenant_id": tenant_id,
                        "created_at": datetime.now(timezone.utc)
                    }
                )
                print(f"✓ 关联用户和角色")
            
            # 5. 创建基础权限
            permissions_data = [
                ("admin", "系统管理", "系统", "系统管理员权限，拥有所有权限"),
                ("kb:read", "查看知识库", "知识库", "查看知识库列表和详情"),
                ("kb:write", "编辑知识库", "知识库", "创建、编辑知识库"),
                ("kb:delete", "删除知识库", "知识库", "删除知识库"),
                ("doc:read", "查看文档", "文档", "查看文档列表和内容"),
                ("doc:write", "编辑文档", "文档", "上传、编辑文档"),
                ("doc:delete", "删除文档", "文档", "删除文档"),
                ("user:read", "查看用户", "用户管理", "查看用户列表和详情"),
                ("user:write", "编辑用户", "用户管理", "创建、编辑用户"),
                ("user:delete", "删除用户", "用户管理", "删除用户"),
                ("role:read", "查看角色", "角色管理", "查看角色列表和详情"),
                ("role:write", "编辑角色", "角色管理", "创建、编辑角色"),
                ("role:delete", "删除角色", "角色管理", "删除角色"),
            ]
            
            permission_ids = []
            for code, name, module, description in permissions_data:
                result = await session.execute(
                    select(Permission).where(
                        Permission.tenant_id == tenant_id,
                        Permission.code == code
                    )
                )
                perm = result.scalar_one_or_none()
                
                if not perm:
                    perm_id = uuid4()
                    perm = Permission(
                        id=perm_id,
                        tenant_id=tenant_id,
                        code=code,
                        name=name,
                        module=module,
                        description=description,
                        created_by_id=admin_id,
                        created_by_name="超级管理员",
                        updated_by_id=admin_id,
                        updated_by_name="超级管理员"
                    )
                    session.add(perm)
                    permission_ids.append(perm_id)
                else:
                    permission_ids.append(perm.id)
            
            await session.flush()
            print(f"✓ 创建 {len(permissions_data)} 个基础权限")
            
            # 6. 将所有权限授予超级管理员角色
            for perm_id in permission_ids:
                result = await session.execute(
                    text("""
                        SELECT 1 FROM role_permissions 
                        WHERE role_id = :role_id AND permission_id = :permission_id
                    """),
                    {"role_id": role.id, "permission_id": perm_id}
                )
                if not result.scalar_one_or_none():
                    await session.execute(
                        text("""
                            INSERT INTO role_permissions (role_id, permission_id, tenant_id, created_at)
                            VALUES (:role_id, :permission_id, :tenant_id, :created_at)
                        """),
                        {
                            "role_id": role.id,
                            "permission_id": perm_id,
                            "tenant_id": tenant_id,
                            "created_at": datetime.now(timezone.utc)
                        }
                    )
            
            print(f"✓ 授予角色所有权限")
            
            # 提交事务
            await session.commit()
            
            # 输出初始化信息
            print("\n" + "=" * 60)
            print("超级管理员初始化完成！")
            print("=" * 60)
            print(f"租户 ID: {tenant_id}")
            print(f"租户名称: {tenant_name}")
            print("-" * 60)
            print(f"管理员 ID: {admin_id}")
            print(f"用户名: {username}")
            print(f"密码: {password}")
            print(f"邮箱: {email}")
            print("=" * 60)
            print("⚠️  请立即登录并修改默认密码！")
            print("=" * 60)
            
            # 保存初始化信息到文件
            output_file = Path("admin_credentials.txt")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"初始化时间: {datetime.now().isoformat()}\n")
                f.write(f"租户 ID: {tenant_id}\n")
                f.write(f"租户名称: {tenant_name}\n")
                f.write(f"管理员 ID: {admin_id}\n")
                f.write(f"用户名: {username}\n")
                f.write(f"密码: {password}\n")
                f.write(f"邮箱: {email}\n")
                f.write("\n⚠️  请妥善保管此文件，并在首次登录后立即删除！\n")
            
            print(f"\n✓ 凭证已保存到: {output_file.absolute()}")
            
        except Exception as e:
            await session.rollback()
            print(f"\n✗ 初始化失败: {e}")
            raise
        finally:
            await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="初始化超级管理员")
    parser.add_argument("--username", default=os.getenv("ADMIN_USERNAME", "admin"), help="管理员用户名")
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD", "Admin@123456"), help="管理员密码")
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL", "admin@genesis-ai.com"), help="管理员邮箱")
    parser.add_argument("--tenant", default=os.getenv("TENANT_NAME", "Default Tenant"), help="租户名称")
    
    args = parser.parse_args()
    
    # 运行初始化
    asyncio.run(init_super_admin(
        username=args.username,
        password=args.password,
        email=args.email,
        tenant_name=args.tenant
    ))


if __name__ == "__main__":
    main()
