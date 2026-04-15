# 工具函数说明

## 密码工具 (password.py)

提供密码哈希生成和验证功能，使用 bcrypt 算法（轮数 12）。

### 在代码中使用

```python
from utils.password import hash_password, verify_password

# 生成密码哈希
hashed = hash_password("Admin@123456")
print(hashed)  # $2b$12$...

# 验证密码
is_valid = verify_password("Admin@123456", hashed)
print(is_valid)  # True
```

### 命令行工具

#### 方式 1：使用 scripts 脚本（推荐）

```powershell
# 交互式输入（密码不会显示）
python scripts/generate_password_hash.py

# 命令行参数
python scripts/generate_password_hash.py Admin@123456

# 使用 uv
uv run python scripts/generate_password_hash.py Admin@123456
```

#### 方式 2：直接运行模块

```powershell
# 需要提供密码参数
python -m utils.password Admin@123456
```

### 输出示例

```
================================================================================
密码哈希生成工具
================================================================================

正在生成哈希...

================================================================================
生成成功
================================================================================
明文密码: Admin@123456
哈希值:   $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqYr8PQWGS
验证结果: ✓ 通过
================================================================================

使用示例:
  1. 复制哈希值到 SQL 脚本:
     password_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqYr8PQWGS'

  2. 在 Python 代码中使用:
     from utils.password import hash_password
     hashed = hash_password('Admin@123456')

提示: 请妥善保管密码，不要在代码中硬编码明文密码！
================================================================================
```

### 安全提示

1. **不要在代码中硬编码明文密码**
2. **不要将密码提交到 Git 仓库**
3. **使用环境变量或配置文件管理敏感信息**
4. **定期更换密码**
5. **使用强密码（包含大小写字母、数字、特殊字符）**

### 与 core.security.crypto 的关系

`utils.password` 模块与 `core.security.crypto` 使用相同的密码上下文配置，确保一致性：

```python
# 两者使用相同的配置
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

这意味着：
- 使用 `utils.password.hash_password()` 生成的哈希可以被 `core.security.crypto.verify_password()` 验证
- 反之亦然

### 常见用途

1. **生成初始管理员密码哈希**（用于 SQL 脚本）
2. **测试密码验证逻辑**
3. **批量生成用户密码**
4. **密码迁移工具**
