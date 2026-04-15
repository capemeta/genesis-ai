"""
安全工具
密码哈希等

密码哈希算法：
- Argon2id（2015 年密码哈希竞赛冠军，OWASP 推荐）

Argon2id 配置：
- memory_cost: 65536 (64 MB) - 防止 GPU/ASIC 并行攻击
- time_cost: 3 - 迭代次数，平衡安全性和性能
- parallelism: 4 - 并行线程数
- hash_len: 32 - 哈希输出长度（256 位）

安全特性：
- 无密码长度限制（bcrypt 限制 72 字节）
- 抗侧信道攻击（Argon2id 变体）
- 内存硬度（Memory-hard），GPU/ASIC 攻击成本高
- 抗 GPU/ASIC 暴力破解

为什么选择 Argon2id：
1. 现代标准：2015 年密码哈希竞赛冠军，被 OWASP、NIST 推荐
2. 内存硬度：需要大量内存，GPU/ASIC 攻击成本极高
3. 侧信道防护：Argon2id 结合了 Argon2i（抗侧信道）和 Argon2d（抗 GPU）
4. 无长度限制：不像 bcrypt 限制 72 字节
5. 可配置性：可根据硬件性能调整安全参数
"""
from passlib.context import CryptContext


# 密码上下文（纯 Argon2id）
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    
    # Argon2id 配置（OWASP 推荐参数）
    argon2__memory_cost=65536,      # 64 MB（推荐范围：64-128 MB）
    argon2__time_cost=3,            # 3 次迭代（推荐范围：2-4）
    argon2__parallelism=4,          # 4 个并行线程（推荐范围：2-8）
    argon2__hash_len=32,            # 32 字节（256 位）
    argon2__type="id",              # 使用 Argon2id 变体（抗侧信道 + 抗 GPU）
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码（Argon2id）
    
    Args:
        plain_password: 明文密码
        hashed_password: Argon2id 哈希密码
    
    Returns:
        bool: 密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    获取密码哈希（使用 Argon2id）
    
    Argon2id 特性：
    - 无密码长度限制（bcrypt 限制 72 字节）
    - 内存硬度（Memory-hard），抗 GPU/ASIC 攻击
    - 抗侧信道攻击
    
    Args:
        password: 明文密码
    
    Returns:
        str: Argon2id 哈希（格式：$argon2id$v=19$m=65536,t=3,p=4$...）
    """
    return pwd_context.hash(password)
