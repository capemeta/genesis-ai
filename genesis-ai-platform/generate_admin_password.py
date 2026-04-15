"""
生成管理员密码哈希（使用 Argon2id）
"""
from core.security.crypto import get_password_hash

password = "Admin@123456"
password_hash = get_password_hash(password)

print("=" * 60)
print("管理员密码哈希生成（Argon2id）")
print("=" * 60)
print(f"密码: {password}")
print(f"哈希: {password_hash}")
print("=" * 60)
print("\n请使用以下 SQL 更新数据库：")
print("=" * 60)
print(f"""
UPDATE users 
SET password_hash = '{password_hash}'
WHERE username = 'admin';
""")
print("=" * 60)
print("\n提示：")
print("- 使用 Argon2id 算法（OWASP 推荐）")
print("- 内存硬度：64 MB")
print("- 抗 GPU/ASIC 攻击")
print("- 无密码长度限制")
print("=" * 60)
