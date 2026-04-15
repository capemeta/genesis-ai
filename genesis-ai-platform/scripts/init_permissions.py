"""
权限初始化脚本

功能：
1. 初始化系统权限数据（菜单权限 + 功能权限）
2. 支持多租户
3. 可重复执行（幂等性）

使用方法：
    python scripts/init_permissions.py --tenant-id <tenant_id>
    
    或使用环境变量：
    TENANT_ID=<tenant_id> python scripts/init_permissions.py
"""
import asyncio
import sys
import os
from pathlib import Path
from uuid import UUID
from typing import Dict, List, Optional
import argparse

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from models.permission import Permission


# ==================== 系统权限定义 ====================

SYSTEM_PERMISSIONS = [
    # ==================== 菜单权限 ====================
    
    # 顶级菜单：系统管理
    {
        "code": "menu:system",
        "name": "系统管理",
        "type": "menu",
        "module": "系统管理",
        "path": "/system",
        "icon": "Settings",
        "sort_order": 100,
        "description": "系统管理模块，包含用户、角色、权限等管理功能"
    },
    
    # 二级菜单：用户管理
    {
        "code": "menu:system:users",
        "name": "用户管理",
        "type": "menu",
        "module": "系统管理",
        "parent_code": "menu:system",
        "path": "/system/users",
        "icon": "Users",
        "component": "@/features/users",
        "sort_order": 1,
        "description": "用户管理页面，查看和管理系统用户"
    },
    
    # 二级菜单：角色管理
    {
        "code": "menu:system:roles",
        "name": "角色管理",
        "type": "menu",
        "module": "系统管理",
        "parent_code": "menu:system",
        "path": "/system/roles",
        "icon": "Shield",
        "component": "@/features/roles",
        "sort_order": 2,
        "description": "角色管理页面，管理角色和权限分配"
    },
    
    # 二级菜单：权限管理
    {
        "code": "menu:system:permissions",
        "name": "权限管理",
        "type": "menu",
        "module": "系统管理",
        "parent_code": "menu:system",
        "path": "/system/permissions",
        "icon": "Key",
        "component": "@/features/permissions",
        "sort_order": 3,
        "description": "权限管理页面，管理系统权限"
    },
    
    # 顶级菜单：知识库
    {
        "code": "menu:knowledge-base",
        "name": "知识库",
        "type": "menu",
        "module": "知识库",
        "path": "/knowledge-base",
        "icon": "BookOpen",
        "sort_order": 10,
        "description": "知识库管理模块"
    },
    
    # ==================== 用户管理功能权限 ====================
    
    {
        "code": "user:read",
        "name": "查看用户",
        "type": "function",
        "module": "用户管理",
        "api_path": "/api/v1/users/list",
        "http_method": "POST",
        "description": "查看用户列表和详情"
    },
    {
        "code": "user:create",
        "name": "创建用户",
        "type": "function",
        "module": "用户管理",
        "api_path": "/api/v1/users/create",
        "http_method": "POST",
        "description": "创建新用户"
    },
    {
        "code": "user:update",
        "name": "编辑用户",
        "type": "function",
        "module": "用户管理",
        "api_path": "/api/v1/users/update",
        "http_method": "POST",
        "description": "编辑用户信息"
    },
    {
        "code": "user:delete",
        "name": "删除用户",
        "type": "function",
        "module": "用户管理",
        "api_path": "/api/v1/users/delete",
        "http_method": "POST",
        "description": "删除用户"
    },
    {
        "code": "user:reset-password",
        "name": "重置密码",
        "type": "function",
        "module": "用户管理",
        "api_path": "/api/v1/users/reset-password",
        "http_method": "POST",
        "description": "重置用户密码"
    },
    {
        "code": "user:change-status",
        "name": "修改状态",
        "type": "function",
        "module": "用户管理",
        "api_path": "/api/v1/users/change-status",
        "http_method": "POST",
        "description": "启用或停用用户"
    },
    {
        "code": "user:assign-roles",
        "name": "分配角色",
        "type": "function",
        "module": "用户管理",
        "api_path": "/api/v1/users/assign-roles",
        "http_method": "POST",
        "description": "为用户分配角色"
    },
    
    # ==================== 角色管理功能权限 ====================
    
    {
        "code": "role:read",
        "name": "查看角色",
        "type": "function",
        "module": "角色管理",
        "api_path": "/api/v1/roles/list",
        "http_method": "POST",
        "description": "查看角色列表和详情"
    },
    {
        "code": "role:create",
        "name": "创建角色",
        "type": "function",
        "module": "角色管理",
        "api_path": "/api/v1/roles/create",
        "http_method": "POST",
        "description": "创建新角色"
    },
    {
        "code": "role:update",
        "name": "编辑角色",
        "type": "function",
        "module": "角色管理",
        "api_path": "/api/v1/roles/update",
        "http_method": "POST",
        "description": "编辑角色信息"
    },
    {
        "code": "role:delete",
        "name": "删除角色",
        "type": "function",
        "module": "角色管理",
        "api_path": "/api/v1/roles/delete",
        "http_method": "POST",
        "description": "删除角色"
    },
    {
        "code": "role:assign-permissions",
        "name": "分配权限",
        "type": "function",
        "module": "角色管理",
        "api_path": "/api/v1/roles/assign-permissions",
        "http_method": "POST",
        "description": "为角色分配权限"
    },
    
    # ==================== 权限管理功能权限 ====================
    
    {
        "code": "permission:read",
        "name": "查看权限",
        "type": "function",
        "module": "权限管理",
        "api_path": "/api/v1/permissions/list",
        "http_method": "POST",
        "description": "查看权限列表和详情"
    },
    {
        "code": "permission:create",
        "name": "创建权限",
        "type": "function",
        "module": "权限管理",
        "api_path": "/api/v1/permissions/create",
        "http_method": "POST",
        "description": "创建新权限"
    },
    {
        "code": "permission:update",
        "name": "编辑权限",
        "type": "function",
        "module": "权限管理",
        "api_path": "/api/v1/permissions/update",
        "http_method": "POST",
        "description": "编辑权限信息"
    },
    {
        "code": "permission:delete",
        "name": "删除权限",
        "type": "function",
        "module": "权限管理",
        "api_path": "/api/v1/permissions/delete",
        "http_method": "POST",
        "description": "删除权限"
    },
    
    # ==================== 知识库功能权限 ====================
    
    {
        "code": "kb:read",
        "name": "查看知识库",
        "type": "function",
        "module": "知识库",
        "api_path": "/api/v1/knowledge-bases/list",
        "http_method": "POST",
        "description": "查看知识库列表和详情"
    },
    {
        "code": "kb:create",
        "name": "创建知识库",
        "type": "function",
        "module": "知识库",
        "api_path": "/api/v1/knowledge-bases/create",
        "http_method": "POST",
        "description": "创建新知识库"
    },
    {
        "code": "kb:update",
        "name": "编辑知识库",
        "type": "function",
        "module": "知识库",
        "api_path": "/api/v1/knowledge-bases/update",
        "http_method": "POST",
        "description": "编辑知识库信息"
    },
    {
        "code": "kb:delete",
        "name": "删除知识库",
        "type": "function",
        "module": "知识库",
        "api_path": "/api/v1/knowledge-bases/delete",
        "http_method": "POST",
        "description": "删除知识库"
    },
]


# ==================== 初始化逻辑 ====================

async def init_permissions(tenant_id: UUID, session: AsyncSession) -> Dict[str, UUID]:
    """
    初始化权限数据
    
    Args:
        tenant_id: 租户ID
        session: 数据库会话
        
    Returns:
        Dict[str, UUID]: 权限代码到ID的映射
    """
    print(f"🚀 开始初始化权限数据（租户ID: {tenant_id}）...")
    
    # 创建权限映射（code -> id）
    permission_map: Dict[str, UUID] = {}
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    # 第一遍：创建或更新所有权限（不包含父子关系）
    for perm_data in SYSTEM_PERMISSIONS:
        # 提取 parent_code（不存储到数据库）
        parent_code = perm_data.pop("parent_code", None)
        code = perm_data["code"]
        
        # 检查权限是否已存在
        stmt = select(Permission).where(
            Permission.tenant_id == tenant_id,
            Permission.code == code
        )
        result = await session.execute(stmt)
        existing_perm = result.scalar_one_or_none()
        
        if existing_perm:
            # 更新现有权限
            for key, value in perm_data.items():
                if key != "code":  # code 不可修改
                    setattr(existing_perm, key, value)
            # 确保状态字段存在且为正常状态
            if not hasattr(existing_perm, 'status') or existing_perm.status is None:
                existing_perm.status = 0
            permission_map[code] = existing_perm.id
            updated_count += 1
            print(f"  ✏️  更新权限: {code}")
        else:
            # 创建新权限
            permission = Permission(
                tenant_id=tenant_id,
                status=0,  # 设置默认状态为正常
                **perm_data
            )
            session.add(permission)
            await session.flush()  # 立即获取 ID
            permission_map[code] = permission.id
            created_count += 1
            print(f"  ✅ 创建权限: {code}")
        
        # 恢复 parent_code（用于第二遍处理）
        if parent_code:
            perm_data["parent_code"] = parent_code
    
    # 第二遍：设置父子关系
    for perm_data in SYSTEM_PERMISSIONS:
        parent_code = perm_data.get("parent_code")
        if parent_code:
            code = perm_data["code"]
            parent_id = permission_map.get(parent_code)
            
            if parent_id:
                # 查询权限并设置父ID
                stmt = select(Permission).where(
                    Permission.tenant_id == tenant_id,
                    Permission.code == code
                )
                result = await session.execute(stmt)
                permission = result.scalar_one()
                permission.parent_id = parent_id
                print(f"  🔗 设置父子关系: {code} -> {parent_code}")
            else:
                print(f"  ⚠️  警告: 找不到父权限 {parent_code}，跳过 {code} 的父子关系设置")
    
    # 提交事务
    await session.commit()
    
    print(f"\n✅ 权限初始化完成！")
    print(f"  - 新建: {created_count} 个")
    print(f"  - 更新: {updated_count} 个")
    print(f"  - 总计: {len(permission_map)} 个")
    
    return permission_map


async def main(tenant_id: str):
    """主函数"""
    try:
        # 转换为 UUID
        tenant_uuid = UUID(tenant_id)
        
        # 获取数据库会话
        async for session in get_async_session():
            # 初始化权限
            permission_map = await init_permissions(tenant_uuid, session)
            
            print(f"\n🎉 初始化成功！共处理 {len(permission_map)} 个权限")
            
    except ValueError as e:
        print(f"❌ 错误: 无效的租户ID格式: {tenant_id}")
        print(f"   请提供有效的 UUID 格式，例如: 123e4567-e89b-12d3-a456-426614174000")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 初始化失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="初始化系统权限数据")
    parser.add_argument(
        "--tenant-id",
        type=str,
        help="租户ID（UUID格式）",
        default=os.getenv("TENANT_ID")
    )
    
    args = parser.parse_args()
    
    if not args.tenant_id:
        print("❌ 错误: 请提供租户ID")
        print("\n使用方法:")
        print("  python scripts/init_permissions.py --tenant-id <tenant_id>")
        print("  或设置环境变量: TENANT_ID=<tenant_id> python scripts/init_permissions.py")
        sys.exit(1)
    
    # 运行初始化
    asyncio.run(main(args.tenant_id))
