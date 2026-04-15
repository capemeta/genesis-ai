# Session 存储优化说明

## 优化目标

1. **区分 key 前缀**：使用 `auth:access:` 和 `auth:refresh:` 更清晰
2. **减少冗余字段**：Refresh session 只存储必要信息
3. **缓存用户信息**：Access session 包含完整用户信息，避免每次请求查数据库
4. **提升性能**：减少数据库查询，提高响应速度
5. **支持"记住我"**：后端根据参数返回不同过期时间的 token
6. **滑动过期**：持续使用时自动续期（Token Rotation）

## Redis Key 设计

### 优化后的 Key 结构

```
# Session 数据（区分 access 和 refresh）
auth:access:{session_id}            # Access Session 数据
auth:refresh:{session_id}           # Refresh Session 数据

# 用户会话管理
auth:user:sessions:{user_id}        # 用户的所有 session ID（Set）

# 安全机制
auth:refresh:revoked:{session_id}   # 已撤销的 refresh token（重放检测）
auth:refresh:lock:{session_id}      # 刷新锁（防止并发）
```

### 优势

1. **一目了然**：从 key 就能看出是 access 还是 refresh session
2. **便于管理**：可以单独扫描 access 或 refresh session
3. **便于监控**：可以分别统计 access 和 refresh session 数量
4. **便于调试**：Redis CLI 中更容易查找和区分

## 优化前后对比

### 优化前

```json
// Access Session
{
  "session_id": "xxx",
  "session_type": "access",
  "user_id": "...",
  "tenant_id": "...",
  "client_ip": "...",
  "user_agent": "...",
  "scope": [...],
  "created_at": "...",
  "expires_at": "...",
  "refresh_session_id": "yyy",
  "token_family_id": "zzz"
}

// Refresh Session（完全重复）
{
  "session_id": "yyy",
  "session_type": "refresh",
  "user_id": "...",           // 重复
  "tenant_id": "...",         // 重复
  "client_ip": "...",         // 重复
  "user_agent": "...",        // 重复
  "scope": [...],             // 重复
  "created_at": "...",
  "expires_at": "...",
  "token_family_id": "zzz",   // 重复
  "access_session_id": "xxx"
}

// 每次请求都需要查数据库获取用户信息
// Token 过期时间固定（Access: 30分钟，Refresh: 3天）
```

### 优化后

```json
// Access Session（包含用户信息缓存 + 自定义过期时间）
{
  "session_id": "xxx",
  "session_type": "access",
  "user_id": "...",
  "tenant_id": "...",
  "client_ip": "...",
  "user_agent": "...",
  "scope": [...],
  "created_at": "...",
  "expires_at": "...",        // 🔥 根据 remember_me 动态设置（30分钟或2小时）
  "refresh_session_id": "yyy",
  "token_family_id": "zzz",
  "user": {                    // 🔥 新增：用户信息缓存
    "id": "...",
    "username": "...",
    "email": "...",
    "nickname": "...",
    "is_active": true,
    "is_superuser": false,
    "avatar_url": "..."
  }
}

// Refresh Session（最小化存储 + 自定义过期时间）
{
  "session_id": "yyy",
  "session_type": "refresh",
  "user_id": "...",
  "tenant_id": "...",
  "scope": [...],
  "created_at": "...",
  "expires_at": "...",        // 🔥 根据 remember_me 动态设置（3天或30天）
  "token_family_id": "zzz",
  "access_session_id": "xxx"
  // 🔥 移除：client_ip, user_agent（从 access session 继承）
}

// 每次请求直接从 Redis 读取用户信息，无需查数据库
// Token 过期时间根据"记住我"动态设置
// 滑动过期：持续使用时自动续期（Token Rotation）
```

## "记住我"功能实现

### 设计理念

**前后端协同**：
- 前端：统一使用 `localStorage` 存储 token（解决新标签页共享问题）
- 后端：根据 `remember_me` 参数返回不同过期时间的 token
- 通过 token 过期时间控制会话长度，而非存储位置

### 过期时间配置

```python
# core/config/settings.py

# 不记住我（短期会话）
ACCESS_TOKEN_EXPIRE_MINUTES = 30              # 30分钟
REFRESH_TOKEN_EXPIRE_DAYS = 3                 # 3天

# 记住我（长期会话）
ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER = 120    # 2小时
REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER = 30       # 30天
```

### 登录时创建 Session

```python
# api/v1/auth.py
@router.post("/login")
async def login(login_data: LoginRequest, ...):
    # 根据"记住我"设置不同的过期时间
    if login_data.remember_me:
        # 记住我：长期会话
        access_expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER)
        refresh_expire = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER)
    else:
        # 不记住：短期会话
        access_expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_expire = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    # 准备用户信息（缓存在 access session 中）
    user_info = {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "nickname": user.nickname,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "avatar_url": user.avatar_url,
    }
    
    # 创建 session 对（传递自定义过期时间）
    session_data = await session_service.create_session_pair(
        user_id=user.id,
        tenant_id=user.tenant_id,
        client_ip=client_ip,
        user_agent=user_agent,
        scope=scope,
        user_info=user_info,
        custom_access_expire=access_expire,   # 🔥 自定义过期时间
        custom_refresh_expire=refresh_expire,  # 🔥 自定义过期时间
    )
    
    return Token(**session_data)
```

### 滑动过期机制

**Token Rotation**：
- 每次刷新 token 时，旧的 refresh token 失效
- 新的 refresh token 有完整的有效期（3天或30天）
- 只要持续使用，token 会不断续期

**实际效果**：
```
不记住我（3天滑动过期）：
- 持续使用：可以无限期登录（每次刷新续期3天）
- 连续3天不用：需要重新登录

记住我（30天滑动过期）：
- 持续使用：可以无限期登录（每次刷新续期30天）
- 连续30天不用：需要重新登录
```

### 前端存储

**统一使用 localStorage**：
```typescript
// token-storage.ts
class TokenStorage {
  setToken(token: string, expiresIn: number): void {
    // 统一存储在 localStorage
    localStorage.setItem(TOKEN_KEY, token)
    const expiresAt = Date.now() + expiresIn * 1000
    localStorage.setItem(TOKEN_EXPIRES_AT_KEY, expiresAt.toString())
  }
  
  getToken(): string | null {
    // 从 localStorage 读取
    return localStorage.getItem(TOKEN_KEY)
  }
}
```

**优势**：
- ✅ 所有标签页共享登录状态
- ✅ 刷新页面不丢失登录状态
- ✅ 支持多端（Web/App/小程序）
- ✅ 实现简单，无需复杂的 fallback 逻辑

## 性能提升

### 数据库查询减少

**优化前**：
- 每次 API 请求：1 次 Redis 查询 + 1 次 PostgreSQL 查询
- 1000 QPS → 1000 次数据库查询/秒

**优化后**：
- 每次 API 请求：1 次 Redis 查询
- 1000 QPS → 0 次数据库查询/秒（用户信息从缓存读取）

### 响应时间优化

- Redis 查询：~1ms
- PostgreSQL 查询：~5-10ms
- **节省时间**：每次请求节省 5-10ms

### 空间消耗

**Access Session**：
- 增加用户信息：约 200 字节
- 可接受（用户信息是高频访问数据）

**Refresh Session**：
- 减少冗余字段：约 100 字节
- 节省空间

**总体**：每个会话对增加约 100 字节，但性能提升显著

## 数据一致性处理

### 问题：用户信息更新后，session 中的数据会过期

**解决方案**：

1. **Access Token 短期有效**（30 分钟）
   - 用户信息最多延迟 30 分钟更新
   - 对大多数场景可接受

2. **Refresh Token 时重新查询**
   - 每次刷新 token 时，从数据库查询最新用户信息
   - 确保数据最终一致性

3. **关键操作强制刷新**
   - 修改密码：撤销所有 session，强制重新登录
   - 禁用用户：撤销所有 session
   - 修改权限：可选择撤销 session 或等待自然过期

### 实现示例

```python
# 修改密码后，撤销所有 session
async def change_password(user_id: UUID, new_password: str):
    # 1. 更新密码
    await update_user_password(user_id, new_password)
    
    # 2. 撤销所有 session（强制重新登录）
    await session_service.revoke_all_user_sessions(user_id)
```

## 安全考虑

### 不要存储敏感信息

**禁止存储**：
- ❌ `password_hash`
- ❌ `phone`（如果是敏感信息）
- ❌ API keys
- ❌ 其他敏感字段

**可以存储**：
- ✅ `id`, `username`, `email`
- ✅ `nickname`, `avatar_url`
- ✅ `is_active`, `is_superuser`
- ✅ 公开的用户信息

### Session 安全

- Session ID 使用 `secrets.token_urlsafe(32)`（256 位随机）
- Redis 存储，支持快速撤销
- TTL 自动过期
- 重放检测和 Token 轮换

## 使用示例

### 登录时创建 Session

```python
# api/v1/auth.py
user_info = {
    "id": str(user.id),
    "username": user.username,
    "email": user.email,
    "nickname": user.nickname,
    "is_active": user.is_active,
    "is_superuser": user.is_superuser,
    "avatar_url": user.avatar_url,
}

session_data = await session_service.create_session_pair(
    user_id=user.id,
    tenant_id=user.tenant_id,
    client_ip=client_ip,
    user_agent=user_agent,
    scope=scope,
    user_info=user_info,  # 传入用户信息
)
```

### 获取当前用户（无需查数据库）

```python
# core/security/auth.py
async def get_current_user(...) -> User:
    session_data = await session_service.verify_session(session_id)
    
    # 从 session 缓存读取用户信息
    cached_user_info = session_data.get("user")
    
    if cached_user_info:
        # 直接构建 User 对象，无需查数据库
        user = User(
            id=UUID(cached_user_info["id"]),
            username=cached_user_info["username"],
            email=cached_user_info.get("email"),
            # ...
        )
        return user
    
    # 降级方案：从数据库查询（兼容旧 session）
    user = await user_repo.get(UUID(user_id))
    return user
```

### 刷新 Token 时更新用户信息

```python
# api/v1/auth.py
async def refresh_token(...):
    # 1. 验证 refresh session
    refresh_session = await session_service.verify_session(refresh_token)
    user_id = refresh_session.get("user_id")
    
    # 2. 从数据库查询最新用户信息
    user = await db.get(User, UUID(user_id))
    
    user_info = {
        "id": str(user.id),
        "username": user.username,
        # ...
    }
    
    # 3. 创建新 session（包含最新用户信息）
    session_data = await session_service.refresh_session(
        refresh_session_id=refresh_token,
        client_ip=client_ip,
        user_agent=user_agent,
        user_info=user_info,  # 传入最新用户信息
    )
    
    return session_data
```

## 监控建议

### 关键指标

1. **缓存命中率**
   - 监控从 session 读取用户信息的成功率
   - 目标：> 99%

2. **数据库查询减少**
   - 监控 `get_current_user` 的数据库查询次数
   - 目标：接近 0

3. **Session 大小**
   - 监控 access session 的平均大小
   - 目标：< 1KB

### 日志记录

```python
import logging
logger = logging.getLogger(__name__)

# 记录降级到数据库查询的情况
if not cached_user_info:
    logger.warning(
        f"User info not found in session {session_id}, "
        f"falling back to database query"
    )
```

## 最佳实践

1. **Access Token 短期有效**
   - 推荐：15-30 分钟
   - 平衡安全性和用户体验

2. **Refresh Token 长期有效**
   - 推荐：7-30 天
   - 支持"记住我"功能

3. **关键操作强制刷新**
   - 修改密码、权限变更：撤销所有 session
   - 修改昵称、头像：等待自然过期（30 分钟内生效）

4. **监控和告警**
   - 监控缓存命中率
   - 监控数据库查询减少情况
   - 异常时告警

## 总结

这个优化方案：

✅ **减少冗余**：Refresh session 只存储必要字段
✅ **提升性能**：每次请求节省 5-10ms 数据库查询
✅ **降低负载**：数据库查询减少 90%+
✅ **保持安全**：不存储敏感信息，支持快速撤销
✅ **数据一致**：Refresh 时更新，关键操作强制刷新
✅ **向后兼容**：降级方案支持旧 session
✅ **支持"记住我"**：后端控制过期时间，前端统一存储
✅ **滑动过期**：持续使用时自动续期（Token Rotation）
✅ **新标签页共享**：使用 localStorage，所有标签页共享登录状态

这是一个典型的 **Session 缓存用户信息 + 灵活过期策略** 模式，在高并发场景下效果显著，同时提供了良好的用户体验。
