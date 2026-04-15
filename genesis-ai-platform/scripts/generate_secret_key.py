"""
生成安全的 SECRET_KEY
独立脚本，不依赖项目其他模块
"""
import secrets


def generate_secret_key(length: int = 32) -> str:
    """
    生成安全的随机密钥
    
    Args:
        length: 密钥长度（字节数）
    
    Returns:
        Base64 编码的密钥字符串
    """
    return secrets.token_urlsafe(length)


def main():
    """主函数"""
    print("=" * 60)
    print("SECRET_KEY 生成器")
    print("=" * 60)
    print()
    print("为 Genesis AI 平台生成安全的 SECRET_KEY")
    print()
    
    # 生成多个密钥供选择
    print("生成的 SECRET_KEY（请选择一个）:")
    print()
    
    for i in range(3):
        key = generate_secret_key(32)
        print(f"{i + 1}. {key}")
    
    print()
    print("=" * 60)
    print("使用说明:")
    print("=" * 60)
    print()
    print("1. 复制上面生成的任意一个密钥")
    print("2. 打开 .env 文件（如果没有，复制 .env.example）")
    print("3. 设置 SECRET_KEY 变量:")
    print()
    print("   SECRET_KEY=<粘贴生成的密钥>")
    print()
    print("4. 保存文件并重启应用")
    print()
    print("⚠️  重要提示:")
    print("   - 不要在代码中硬编码 SECRET_KEY")
    print("   - 不要将 .env 文件提交到版本控制")
    print("   - 生产环境必须使用强随机密钥")
    print("   - 定期更换密钥以提高安全性")
    print()


if __name__ == "__main__":
    main()
