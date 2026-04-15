#!/usr/bin/env python
"""
生成密码哈希工具

使用方法：
    # 方式 1：交互式输入
    python scripts/generate_password_hash.py
    
    # 方式 2：命令行参数
    python scripts/generate_password_hash.py Admin@123456
    
    # 方式 3：使用 uv
    uv run python scripts/generate_password_hash.py Admin@123456
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.security.crypto import get_password_hash, verify_password


def main():
    """主函数"""
    print("=" * 80)
    print("密码哈希生成工具")
    print("=" * 80)
    print()
    
    # 获取密码
    if len(sys.argv) > 1:
        # 从命令行参数获取
        password = sys.argv[1]
    else:
        # 交互式输入
        import getpass
        password = getpass.getpass("请输入密码: ")
        
        if not password:
            print("错误: 密码不能为空")
            sys.exit(1)
    
    # 生成哈希
    print("\n正在生成哈希...")
    hashed = get_password_hash(password)
    
    # 验证哈希
    is_valid = verify_password(password, hashed)
    
    # 输出结果
    print("\n" + "=" * 80)
    print("生成成功")
    print("=" * 80)
    print(f"明文密码: {password}")
    print(f"哈希值:   {hashed}")
    print(f"验证结果: {'✓ 通过' if is_valid else '✗ 失败'}")
    print("=" * 80)
    print()
    print("使用示例:")
    print("  1. 复制哈希值到 SQL 脚本:")
    print(f"     password_hash = '{hashed}'")
    print()
    print("  2. 在 Python 代码中使用:")
    print(f"     from core.security.crypto import get_password_hash")
    print(f"     hashed = get_password_hash('{password}')")
    print()
    print("提示: 请妥善保管密码，不要在代码中硬编码明文密码！")
    print("=" * 80)


if __name__ == "__main__":
    main()
