#!/usr/bin/env python
"""
简单的密码哈希生成工具（独立脚本）

使用方法：
    python scripts/hash_password_simple.py Admin@123456
"""
import sys


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python scripts/hash_password_simple.py <密码>")
        print("示例: python scripts/hash_password_simple.py Admin@123456")
        sys.exit(1)
    
    password = sys.argv[1]
    
    try:
        import bcrypt
        
        # 使用 bcrypt 直接生成哈希
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        hashed_str = hashed.decode('utf-8')
        
        # 验证
        is_valid = bcrypt.checkpw(password.encode('utf-8'), hashed)
        
        print("=" * 80)
        print("密码哈希生成成功")
        print("=" * 80)
        print(f"明文密码: {password}")
        print(f"哈希值:   {hashed_str}")
        print(f"验证结果: {'✓ 通过' if is_valid else '✗ 失败'}")
        print("=" * 80)
        print()
        print("使用示例:")
        print("  复制哈希值到 SQL 脚本:")
        print(f"  password_hash = '{hashed_str}'")
        print("=" * 80)
        
    except ImportError:
        print("错误: 未安装 bcrypt 库")
        print("请运行: pip install bcrypt")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
