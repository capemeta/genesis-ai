"""
并发控制限流器。

当前阶段：
- 规则来源先使用 .env
- 作用域先启用全局并发
- 支持三种准入模式：立即失败 / 一直等待 / 等待超时

设计目标：
- 所有工作负载统一走同一套并发控制入口
- 通过 lease token + TTL 提升异常场景下的恢复能力
- 为未来接入租户级 / 知识库级 / 模型级规则预留上下文和多 scope 结构
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import time
from typing import Optional
from uuid import uuid4

from redis import ConnectionPool, Redis as SyncRedis

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConcurrencyContext:
    """并发控制上下文。"""

    tenant_id: str | None = None
    kb_id: str | None = None
    kb_doc_id: str | None = None
    provider: str | None = None
    model: str | None = None
    workload_type: str | None = None
    request_source: str | None = None


@dataclass(slots=True)
class ConcurrencyScopeLimit:
    """单个 scope 的并发限制。"""

    key: str
    limit: int


@dataclass(slots=True)
class ConcurrencyPolicy:
    """生效并发策略。"""

    limiter_type: str
    mode: str
    wait_timeout_seconds: int | None
    lease_ttl_seconds: int
    poll_interval_ms: int
    scope_limits: list[ConcurrencyScopeLimit] = field(default_factory=list)


@dataclass(slots=True)
class ConcurrencyLease:
    """并发租约。"""

    limiter_type: str
    lease_id: str
    scope_keys: list[str]
    acquired_at_ms: int
    expire_at_ms: int
    policy: ConcurrencyPolicy


_sync_redis_pool: Optional[ConnectionPool] = None
_sync_redis_client: Optional[SyncRedis] = None

ACQUIRE_LEASE_SCRIPT = """
local lease_id = ARGV[1]
local now_ms = tonumber(ARGV[2])
local expire_at_ms = tonumber(ARGV[3])

for i, key in ipairs(KEYS) do
    local limit = tonumber(ARGV[3 + i])
    redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms)
    local current = redis.call('ZCARD', key)
    if current >= limit then
        return 0
    end
end

local ttl_ms = math.max(expire_at_ms - now_ms, 1000) * 2
for _, key in ipairs(KEYS) do
    redis.call('ZADD', key, expire_at_ms, lease_id)
    redis.call('PEXPIRE', key, ttl_ms)
end

return 1
"""

RELEASE_LEASE_SCRIPT = """
local lease_id = ARGV[1]
for _, key in ipairs(KEYS) do
    redis.call('ZREM', key, lease_id)
end
return 1
"""

RENEW_LEASE_SCRIPT = """
local lease_id = ARGV[1]
local expire_at_ms = tonumber(ARGV[2])
local updated = 0
for _, key in ipairs(KEYS) do
    local exists = redis.call('ZSCORE', key, lease_id)
    if exists then
        redis.call('ZADD', key, expire_at_ms, lease_id)
        updated = 1
    end
end
return updated
"""


def _get_settings():
    from core.config import settings
    return settings


def _get_redis() -> Optional[SyncRedis]:
    """获取同步 Redis 客户端。"""
    global _sync_redis_pool, _sync_redis_client

    try:
        if _sync_redis_client is None:
            settings = _get_settings()
            if _sync_redis_pool is None:
                _sync_redis_pool = ConnectionPool.from_url(
                    settings.REDIS_URL,
                    decode_responses=False,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    max_connections=50,
                    health_check_interval=30,
                )
            _sync_redis_client = SyncRedis(connection_pool=_sync_redis_pool)
        return _sync_redis_client
    except Exception as exc:
        logger.error("[Limiter] 获取 Redis 连接失败: %s", exc)
        return None


def resolve_concurrency_policy(
    limiter_type: str,
    *,
    context: ConcurrencyContext | None = None,
) -> ConcurrencyPolicy:
    """
    解析当前生效并发策略。

    当前阶段仅启用全局 scope，后续可在这里叠加租户 / 知识库 / 模型级规则。
    """
    settings = _get_settings()
    default_ttl = max(30, int(settings.RAG_CONCURRENCY_LEASE_TTL_SECONDS))
    default_poll_interval_ms = max(50, int(settings.RAG_CONCURRENCY_POLL_INTERVAL_MS))

    limit_map = {
        "parse": int(settings.RAG_PARSE_CONCURRENCY),
        "chunk": int(settings.RAG_CHUNK_CONCURRENCY),
        "embed": int(settings.RAG_EMBED_CONCURRENCY),
        "llm": int(settings.RAG_LLM_CONCURRENCY),
        "kg": int(settings.RAG_KG_CONCURRENCY),
        "minio": int(settings.RAG_MINIO_CONCURRENCY),
    }
    limit = max(1, int(limit_map.get(limiter_type, 1)))

    if limiter_type == "llm":
        mode = str(settings.RAG_LLM_CONCURRENCY_MODE or "wait").strip().lower()
        timeout_value = int(settings.RAG_LLM_CONCURRENCY_WAIT_TIMEOUT_SECONDS)
        wait_timeout_seconds = None if mode == "wait" else max(0, timeout_value)
    else:
        mode = "wait_timeout"
        wait_timeout_seconds = 30

    if mode not in {"fail_fast", "wait", "wait_timeout"}:
        mode = "wait"
        wait_timeout_seconds = None

    global_key = f"concurrency:{limiter_type}:global"
    scope_limits = [ConcurrencyScopeLimit(key=global_key, limit=limit)]

    # 未来可在这里按最严格原则继续叠加更多 scope。
    _ = context

    return ConcurrencyPolicy(
        limiter_type=limiter_type,
        mode=mode,
        wait_timeout_seconds=wait_timeout_seconds,
        lease_ttl_seconds=default_ttl,
        poll_interval_ms=default_poll_interval_ms,
        scope_limits=scope_limits,
    )


def try_acquire_concurrency_lease(
    limiter_type: str,
    *,
    context: ConcurrencyContext | None = None,
    policy: ConcurrencyPolicy | None = None,
) -> ConcurrencyLease | None:
    """尝试一次获取并发租约。"""
    redis = _get_redis()
    if not redis:
        logger.warning("[Limiter] Redis 不可用，%s 限流器降级放行", limiter_type)
        return _build_degraded_lease(limiter_type, policy or resolve_concurrency_policy(limiter_type, context=context))

    effective_policy = policy or resolve_concurrency_policy(limiter_type, context=context)
    scope_keys = [item.key for item in effective_policy.scope_limits]
    scope_limits = [str(item.limit) for item in effective_policy.scope_limits]
    lease_id = str(uuid4())
    now_ms = int(time.time() * 1000)
    expire_at_ms = now_ms + effective_policy.lease_ttl_seconds * 1000

    try:
        script = redis.register_script(ACQUIRE_LEASE_SCRIPT)
        result = script(
            keys=scope_keys,
            args=[lease_id, str(now_ms), str(expire_at_ms), *scope_limits],
        )
    except Exception as exc:
        logger.error("[Limiter] 获取 %s 租约失败，降级放行: %s", limiter_type, exc)
        return _build_degraded_lease(limiter_type, effective_policy)

    if result != 1:
        return None

    return ConcurrencyLease(
        limiter_type=limiter_type,
        lease_id=lease_id,
        scope_keys=scope_keys,
        acquired_at_ms=now_ms,
        expire_at_ms=expire_at_ms,
        policy=effective_policy,
    )


def acquire_concurrency_lease(
    limiter_type: str,
    *,
    context: ConcurrencyContext | None = None,
    policy: ConcurrencyPolicy | None = None,
) -> ConcurrencyLease | None:
    """
    按策略获取并发租约。

    返回：
    - 成功：ConcurrencyLease
    - 失败：None
    """
    effective_policy = policy or resolve_concurrency_policy(limiter_type, context=context)
    deadline: float | None = None
    if effective_policy.mode == "wait_timeout" and effective_policy.wait_timeout_seconds is not None:
        deadline = time.time() + effective_policy.wait_timeout_seconds

    while True:
        lease = try_acquire_concurrency_lease(
            limiter_type,
            context=context,
            policy=effective_policy,
        )
        if lease is not None:
            return lease

        if effective_policy.mode == "fail_fast":
            return None

        if deadline is not None and time.time() >= deadline:
            return None

        time.sleep(effective_policy.poll_interval_ms / 1000.0)


def release_concurrency_lease(lease: ConcurrencyLease | None) -> None:
    """释放并发租约。"""
    if lease is None:
        return

    redis = _get_redis()
    if not redis:
        return

    try:
        script = redis.register_script(RELEASE_LEASE_SCRIPT)
        script(keys=lease.scope_keys, args=[lease.lease_id])
    except Exception as exc:
        logger.error("[Limiter] 释放 %s 租约失败: %s", lease.limiter_type, exc)


def renew_concurrency_lease(lease: ConcurrencyLease | None) -> bool:
    """
    续租并发租约。

    适用于：
    - 流式输出
    - 长时间 LLM 推理
    - 长时间持有资源的后台任务
    """
    if lease is None:
        return False

    redis = _get_redis()
    if not redis:
        return True

    now_ms = int(time.time() * 1000)
    expire_at_ms = now_ms + lease.policy.lease_ttl_seconds * 1000
    try:
        script = redis.register_script(RENEW_LEASE_SCRIPT)
        result = script(keys=lease.scope_keys, args=[lease.lease_id, str(expire_at_ms)])
    except Exception as exc:
        logger.error("[Limiter] 续租 %s 租约失败: %s", lease.limiter_type, exc)
        return False

    if result != 1:
        return False

    lease.expire_at_ms = expire_at_ms
    return True


def _build_degraded_lease(limiter_type: str, policy: ConcurrencyPolicy) -> ConcurrencyLease:
    """Redis 不可用时返回降级租约，保证调用链不中断。"""
    now_ms = int(time.time() * 1000)
    expire_at_ms = now_ms + policy.lease_ttl_seconds * 1000
    return ConcurrencyLease(
        limiter_type=limiter_type,
        lease_id=f"degraded:{uuid4()}",
        scope_keys=[item.key for item in policy.scope_limits],
        acquired_at_ms=now_ms,
        expire_at_ms=expire_at_ms,
        policy=policy,
    )


# ==================== 向后兼容包装 ====================

_legacy_leases: dict[str, ConcurrencyLease] = {}


def _legacy_acquire(limiter_type: str) -> bool:
    lease = acquire_concurrency_lease(limiter_type)
    if lease is None:
        return False
    _legacy_leases[limiter_type] = lease
    return True


def _legacy_release(limiter_type: str) -> None:
    lease = _legacy_leases.pop(limiter_type, None)
    release_concurrency_lease(lease)


def acquire_parse_slot(timeout: int = 30) -> bool:
    _ = timeout
    return _legacy_acquire("parse")


def release_parse_slot() -> None:
    _legacy_release("parse")


def acquire_chunk_slot(timeout: int = 30) -> bool:
    _ = timeout
    return _legacy_acquire("chunk")


def release_chunk_slot() -> None:
    _legacy_release("chunk")


def acquire_embed_slot(timeout: int = 30) -> bool:
    _ = timeout
    return _legacy_acquire("embed")


def release_embed_slot() -> None:
    _legacy_release("embed")


def acquire_llm_slot(timeout: int = 30) -> bool:
    _ = timeout
    return _legacy_acquire("llm")


def release_llm_slot() -> None:
    _legacy_release("llm")


def acquire_kg_slot(timeout: int = 30) -> bool:
    _ = timeout
    return _legacy_acquire("kg")


def release_kg_slot() -> None:
    _legacy_release("kg")


def acquire_minio_slot(timeout: int = 30) -> bool:
    _ = timeout
    return _legacy_acquire("minio")


def release_minio_slot() -> None:
    _legacy_release("minio")
