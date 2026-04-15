"""
密码工具模块
提供密码哈希生成和验证功能

注意：此模块是 core.security.crypto 的便捷封装
"""
from core.security.crypto import get_password_hash as hash_password
from core.security.crypto import verify_password

# 导出函数
__all__ = ["hash_password", "verify_password"]


def main():
    """命令行工具：生成密码哈希"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python -m utils.password <密码>")
        print("示例: python -m utils.password Admin@123456")
        sys.exit(1)
    
    password = sys.argv[1]
    hashed = hash_password(password)
    
    print("=" * 80)
    print("密码哈希生成成功")
    print("=" * 80)
    print(f"明文密码: {password}")
    print(f"哈希值:   {hashed}")
    print("=" * 80)
    print("\n提示: 将哈希值复制到 SQL 脚本或代码中使用")


if __name__ == "__main__":
    main()
