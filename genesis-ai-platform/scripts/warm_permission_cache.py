"""
权限缓存预热脚本

功能：
1. 查询所有活跃用户
2. 预热权限缓存到 Redis
3. 提升首次访问性能

使用场景：
- 系统启动后
- 权限数据大量变更后
- Redis 缓存清空后

使用方法：
    python scripts/warm_permission_cache.py
    
    或指定租户：
    python scripts/warm_permission_cache.py --tenant-id <tenant_id>
"""
import asyncio
import sys
import os
from pathlib import Path
from uuid import UUID
from typing import Optional
import argparse

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from models.user import User
from services.permission_service import PermissionService
from core.security.permission_cache import permission_cache


async def warm_cache_for_user(
    user: User,
    session: AsyncSession,
    verbose: bool = False
) -> bool:
    """
    为单个用户预热权限缓存
    
    Args:
        user: 用户对象
        session: 数据库会话
        verbose: 是否显示详细信息
        
    Returns:
        bool: 是否成功
    """
    try:
        service = PermissionService(session)
        
        # 获取用户权限
        permissions = await service.get_user_permissions(
            user.id,
            user.tenant_id
        )
        
        # 写入缓存
        await permission_cache.set_permissions(
            user.id,
            user.tenant_id,
            permissions
        )
        
        if verbose:
            print(f"  ✅ {user.username} ({user.nickname}): {len(permissions)} 个权限")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 预热失败 - {user.username}: {str(e)}")
        return False


async def warm_cache_for_tenant(
    tenant_id: Optional[UUID],
    session: AsyncSession,
    verbose: bool = False
) -> tuple[int, int]:
    """
    为租户的所有用户预热缓存
    
    Args:
        tenant_id: 租户ID（None 表示所有租户）
        session: 数据库会话
        verbose: 是否显示详细信息
        
    Returns:
        tuple[int, int]: (成功数量, 失败数量)
    """
    # 构建查询
    stmt = select(User).where(User.status == 'active')
    
    if tenant_id:
        stmt = stmt.where(User.tenant_id == tenant_id)
        print(f"🔍 查询租户 {tenant_id} 的活跃用户...")
    else:
        print(f"🔍 查询所有租户的活跃用户...")
    
    # 执行查询
    result = await session.execute(stmt)
    users = result.scalars().all()
    
    if not users:
        print("⚠️  未找到活跃用户")
        return 0, 0
    
    print(f"📊 找到 {len(users)} 个活跃用户")
    print(f"🚀 开始预热权限缓存...\n")
    
    # 预热缓存
    success_count = 0
    failed_count = 0
    
    for user in users:
        success = await warm_cache_for_user(user, session, verbose)
        if success:
            success_count += 1
        else:
            failed_count += 1
    
    return success_count, failed_count


async def main(tenant_id: Optional[str] = None, verbose: bool = False):
    """主函数"""
    try:
        # 转换租户ID
        tenant_uuid = UUID(tenant_id) if tenant_id else None
        
        # 获取数据库会话
        async for session in get_async_session():
            # 预热缓存
            success_count, failed_count = await warm_cache_for_tenant(
                tenant_uuid,
                session,
                verbose
            )
            
            # 输出结果
            print(f"\n{'='*50}")
            print(f"✅ 预热完成！")
            print(f"  - 成功: {success_count} 个用户")
            if failed_count > 0:
                print(f"  - 失败: {failed_count} 个用户")
            print(f"  - 总计: {success_count + failed_count} 个用户")
            print(f"{'='*50}\n")
            
            if failed_count > 0:
                print("⚠️  部分用户预热失败，请检查日志")
                sys.exit(1)
            
    except ValueError as e:
        print(f"❌ 错误: 无效的租户ID格式: {tenant_id}")
        print(f"   请提供有效的 UUID 格式")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 预热失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="预热权限缓存")
    parser.add_argument(
        "--tenant-id",
        type=str,
        help="租户ID（UUID格式），不指定则预热所有租户",
        default=None
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细信息"
    )
    
    args = parser.parse_args()
    
    # 运行预热
    print("🔥 权限缓存预热工具\n")
    asyncio.run(main(args.tenant_id, args.verbose))
