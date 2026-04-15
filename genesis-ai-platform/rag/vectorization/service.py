"""
检索投影向量化服务。

职责：
- 统一按知识库运行时模型解析 embedding 模型
- 统一调用模型中心 embedding 入口
- 为短期热点文本提供 Redis 缓存
- 将向量写入 pg_chunk_search_unit_vectors

设计约束：
- Redis 只做短期热缓存，不做永久向量存储
- 向量物理存储仍以 PostgreSQL 为准
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Iterable
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.model_platform.kb_model_resolver import resolve_kb_runtime_model
from models.chunk_search_unit import ChunkSearchUnit
from models.knowledge_base import KnowledgeBase
from models.platform_model import PlatformModel
from models.tenant_model import TenantModel
from models.tenant_model_provider import TenantModelProvider
from rag.pgvector_utils import (
    build_vector_cast_type,
    ensure_pgvector_dimension_compatible,
    get_pgvector_embedding_dimension,
)
from services.model_platform_service import ModelInvocationService

logger = logging.getLogger(__name__)
VECTOR_UPSERT_BATCH_SIZE = 20

EMBED_CACHE_VERSION = "v2"
EMBED_CACHE_NAMESPACE = "rag:embed-cache"
EMBED_CACHE_INDEX_KEY = f"{EMBED_CACHE_NAMESPACE}:index"
EMBED_CACHE_LOCK_NAMESPACE = f"{EMBED_CACHE_NAMESPACE}:lock"
EMBED_CACHE_LOCK_TTL_SECONDS = 30
EMBED_CACHE_LOCK_WAIT_SECONDS = 5
EMBED_CACHE_LOCK_POLL_SECONDS = 0.1


@dataclass(slots=True)
class EmbeddingModelSnapshot:
    """当前向量化使用的模型快照。"""

    tenant_model_id: UUID
    platform_model_id: UUID
    raw_model_name: str
    display_name: str
    embedding_dimension: int | None
    cache_signature: str


@dataclass(slots=True)
class EmbeddingBuildStats:
    """本次向量化统计。"""

    vectorized_count: int = 0
    cache_hit_count: int = 0
    cache_miss_count: int = 0
    skipped_count: int = 0


class SearchUnitEmbeddingService:
    """检索投影向量化服务。"""

    def __init__(self, session: AsyncSession, *, redis_client: Redis | None = None):
        self.session = session
        self.redis = redis_client
        self.model_invocation_service = ModelInvocationService(session)

    async def build_vectors_for_chunk_ids(
        self,
        *,
        kb: KnowledgeBase,
        chunk_ids: list[int],
    ) -> dict[str, Any]:
        """为指定 chunk 的检索投影构建向量。"""
        if not chunk_ids:
            return {
                "vectorized_count": 0,
                "cache_hit_count": 0,
                "cache_miss_count": 0,
                "skipped_count": 0,
                "model_name": None,
                "embedding_dimension": None,
            }

        search_units = await self._load_search_units(chunk_ids)
        if not search_units:
            return {
                "vectorized_count": 0,
                "cache_hit_count": 0,
                "cache_miss_count": 0,
                "skipped_count": 0,
                "model_name": None,
                "embedding_dimension": None,
            }

        model_snapshot = await self._resolve_embedding_model(kb)
        index_dimension = await get_pgvector_embedding_dimension(self.session)
        stats = EmbeddingBuildStats()
        vector_rows: list[dict[str, Any]] = []
        total_units = len(search_units)

        logger.info(
            "[VectorizeTask] 检索投影加载完成: chunk_count=%s, search_unit_count=%s, model=%s, index_dimension=%s",
            len(chunk_ids),
            total_units,
            model_snapshot.display_name,
            index_dimension,
        )

        for index, search_unit in enumerate(search_units, start=1):
            metadata = dict(search_unit.metadata_info or {})
            should_vectorize = bool(metadata.get("should_vectorize", True))
            if not should_vectorize:
                stats.skipped_count += 1
                logger.info(
                    "[VectorizeTask] 跳过检索投影: progress=%s/%s, search_unit_id=%s, chunk_id=%s, scope=%s, reason=should_vectorize_false",
                    index,
                    total_units,
                    search_unit.id,
                    search_unit.chunk_id,
                    search_unit.search_scope,
                )
                continue

            embedding_text = self._resolve_embedding_text(search_unit=search_unit, metadata=metadata)
            text_length = len(embedding_text)
            text_hash = hashlib.sha256(embedding_text.encode("utf-8")).hexdigest()[:12]
            unit_started_at = time.perf_counter()
            logger.info(
                "[VectorizeTask] 开始处理检索投影: progress=%s/%s, search_unit_id=%s, chunk_id=%s, scope=%s, text_length=%s, text_hash=%s",
                index,
                total_units,
                search_unit.id,
                search_unit.chunk_id,
                search_unit.search_scope,
                text_length,
                text_hash,
            )
            embedding, cache_hit = await self._embed_single_text(
                kb=kb,
                model_snapshot=model_snapshot,
                text=embedding_text,
            )
            dimension = len(embedding)
            await self._ensure_model_embedding_dimension(model_snapshot, actual_dimension=dimension)
            self._validate_embedding_dimension(
                model_snapshot,
                actual_dimension=dimension,
                index_dimension=index_dimension,
            )
            vector_rows.append(
                {
                    "tenant_id": str(search_unit.tenant_id),
                    "kb_id": str(search_unit.kb_id),
                    "search_unit_id": int(search_unit.id),
                    "model_id": str(model_snapshot.tenant_model_id),
                    "model_name": model_snapshot.raw_model_name,
                    "vector_scope": str(search_unit.search_scope),
                    "embedding_dimension": dimension,
                    "embedding": self._format_vector_literal(embedding),
                    "content_hash": hashlib.sha256(embedding_text.encode("utf-8")).hexdigest(),
                    "metadata": json.dumps(
                        {
                            "search_scope": search_unit.search_scope,
                            "is_primary": bool(search_unit.is_primary),
                            "priority": int(search_unit.priority or 100),
                            "cache_hit": cache_hit,
                        },
                        ensure_ascii=False,
                    ),
                }
            )
            stats.vectorized_count += 1
            if cache_hit:
                stats.cache_hit_count += 1
            else:
                stats.cache_miss_count += 1
            elapsed_ms = int((time.perf_counter() - unit_started_at) * 1000)
            logger.info(
                "[VectorizeTask] 检索投影处理完成: progress=%s/%s, search_unit_id=%s, chunk_id=%s, scope=%s, cache_hit=%s, embedding_dimension=%s, elapsed_ms=%s",
                index,
                total_units,
                search_unit.id,
                search_unit.chunk_id,
                search_unit.search_scope,
                cache_hit,
                dimension,
                elapsed_ms,
            )
            if elapsed_ms >= 10000:
                logger.warning(
                    "[VectorizeTask] 检索投影处理耗时过长: progress=%s/%s, search_unit_id=%s, chunk_id=%s, scope=%s, elapsed_ms=%s",
                    index,
                    total_units,
                    search_unit.id,
                    search_unit.chunk_id,
                    search_unit.search_scope,
                    elapsed_ms,
                )

        if vector_rows:
            await self._upsert_vectors(vector_rows, index_dimension=index_dimension)

        return {
            "vectorized_count": stats.vectorized_count,
            "cache_hit_count": stats.cache_hit_count,
            "cache_miss_count": stats.cache_miss_count,
            "skipped_count": stats.skipped_count,
            "model_name": model_snapshot.raw_model_name,
            "embedding_dimension": model_snapshot.embedding_dimension,
        }

    def _resolve_embedding_text(
        self,
        *,
        search_unit: ChunkSearchUnit,
        metadata: dict[str, Any],
    ) -> str:
        """解析向量化实际使用的文本。"""
        preferred_text = str(metadata.get("vector_text") or "").strip()
        if preferred_text:
            return preferred_text
        fallback_text = str(search_unit.search_text or "").strip()
        if fallback_text:
            return fallback_text
        raise RuntimeError("检索投影文本为空，无法生成向量")

    async def _load_search_units(self, chunk_ids: list[int]) -> list[ChunkSearchUnit]:
        """加载需要向量化的检索投影。"""
        stmt = (
            select(ChunkSearchUnit)
            .where(
                ChunkSearchUnit.chunk_id.in_(chunk_ids),
                ChunkSearchUnit.is_active == True,  # noqa: E712
            )
            .order_by(ChunkSearchUnit.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _resolve_embedding_model(self, kb: KnowledgeBase) -> EmbeddingModelSnapshot:
        """解析知识库当前实际使用的 embedding 模型。"""
        resolved = await resolve_kb_runtime_model(self.session, kb=kb, capability_type="embedding")
        stmt = (
            select(TenantModel, PlatformModel, TenantModelProvider)
            .join(PlatformModel, PlatformModel.id == TenantModel.platform_model_id)
            .join(TenantModelProvider, TenantModelProvider.id == TenantModel.tenant_provider_id)
            .where(TenantModel.id == resolved.tenant_model_id)
        )
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            raise RuntimeError("未找到知识库运行时嵌入模型，请检查模型中心配置")

        tenant_model, platform_model, tenant_provider = row
        return EmbeddingModelSnapshot(
            tenant_model_id=resolved.tenant_model_id,
            platform_model_id=platform_model.id,
            raw_model_name=str(platform_model.raw_model_name or resolved.raw_model_name),
            display_name=str(tenant_model.model_alias or platform_model.display_name or platform_model.raw_model_name),
            embedding_dimension=platform_model.embedding_dimension,
            cache_signature=self._build_cache_signature(
                tenant_model=tenant_model,
                platform_model=platform_model,
                tenant_provider=tenant_provider,
            ),
        )

    async def _embed_single_text(
        self,
        *,
        kb: KnowledgeBase,
        model_snapshot: EmbeddingModelSnapshot,
        text: str,
    ) -> tuple[list[float], bool]:
        """对单条文本做 embedding，优先命中缓存。"""
        normalized_text = str(text or "").strip()
        if not normalized_text:
            raise RuntimeError("检索投影文本为空，无法生成向量")

        cache_key = self._build_cache_key(
            model_snapshot.tenant_model_id,
            model_snapshot.cache_signature,
            normalized_text,
        )
        should_use_cache = self._should_use_cache(normalized_text) and self.redis is not None
        if should_use_cache:
            cached = await self.redis.get(cache_key)
            if cached:
                payload = json.loads(cached)
                cached_signature = str(payload.get("cache_signature") or "").strip()
                if cached_signature and cached_signature != model_snapshot.cache_signature:
                    logger.info("Embedding 热缓存签名已变更，跳过旧缓存 tenant_model_id=%s", model_snapshot.tenant_model_id)
                else:
                    embedding = [float(item) for item in list(payload.get("embedding") or [])]
                    if embedding:
                        return embedding, True

        lock_key = self._build_cache_lock_key(cache_key)
        lock_token: str | None = None
        if should_use_cache:
            lock_token = await self._acquire_cache_lock(lock_key)
            if lock_token is None:
                cached_embedding = await self._wait_for_cached_embedding(
                    cache_key=cache_key,
                    expected_signature=model_snapshot.cache_signature,
                )
                if cached_embedding:
                    return cached_embedding, True

        current_user = SimpleNamespace(
            tenant_id=kb.tenant_id,
            id=None,
            nickname="System",
            username="system",
        )
        invoke_started_at = time.perf_counter()
        logger.info(
            "[VectorizeTask] 调用 embedding 模型: model=%s, tenant_model_id=%s, text_length=%s",
            model_snapshot.display_name,
            model_snapshot.tenant_model_id,
            len(normalized_text),
        )
        try:
            response = await self.model_invocation_service.embed(
                current_user=current_user,
                tenant_model_id=model_snapshot.tenant_model_id,
                capability_type="embedding",
                input_texts=[normalized_text],
                request_source="kb_vector_index_build",
            )
            data_items = list(response.get("data") or [])
            if not data_items:
                raise RuntimeError("Embedding 响应为空，未返回 data")
            embedding = [float(item) for item in list((data_items[0] or {}).get("embedding") or [])]
            if not embedding:
                raise RuntimeError("Embedding 响应为空，未返回有效向量")

            if should_use_cache:
                await self._cache_embedding(
                    cache_key=cache_key,
                    embedding=embedding,
                    dimension=len(embedding),
                    tenant_model_id=model_snapshot.tenant_model_id,
                    cache_signature=model_snapshot.cache_signature,
                )
            invoke_elapsed_ms = int((time.perf_counter() - invoke_started_at) * 1000)
            logger.info(
                "[VectorizeTask] embedding 模型调用完成: model=%s, tenant_model_id=%s, dimension=%s, elapsed_ms=%s",
                model_snapshot.display_name,
                model_snapshot.tenant_model_id,
                len(embedding),
                invoke_elapsed_ms,
            )
            return embedding, False
        finally:
            if lock_token is not None:
                await self._release_cache_lock(lock_key, lock_token)

    async def _cache_embedding(
        self,
        *,
        cache_key: str,
        embedding: list[float],
        dimension: int,
        tenant_model_id: UUID,
        cache_signature: str,
    ) -> None:
        """写入 Redis 热缓存，并按最大条数裁剪。"""
        if self.redis is None or not settings.RAG_EMBED_CACHE_ENABLED:
            return

        payload = json.dumps(
            {
                "embedding": embedding,
                "dimension": dimension,
                "tenant_model_id": str(tenant_model_id),
                "cache_signature": cache_signature,
                "cached_at": int(time.time()),
            },
            ensure_ascii=False,
        )
        ttl_seconds = max(60, settings.RAG_EMBED_CACHE_TTL_SECONDS)
        now = time.time()
        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.setex(cache_key, ttl_seconds, payload)
            await pipe.zadd(EMBED_CACHE_INDEX_KEY, {cache_key: now})
            await pipe.expire(EMBED_CACHE_INDEX_KEY, ttl_seconds)
            await pipe.execute()

        await self._trim_cache_if_needed()

    async def _trim_cache_if_needed(self) -> None:
        """按全局最大缓存条数裁剪最老的 embedding 缓存。"""
        if self.redis is None or not settings.RAG_EMBED_CACHE_ENABLED:
            return

        max_items = max(100, settings.RAG_EMBED_CACHE_MAX_ITEMS)
        current_size = await self.redis.zcard(EMBED_CACHE_INDEX_KEY)
        overflow = current_size - max_items
        if overflow <= 0:
            return

        stale_keys = await self.redis.zrange(EMBED_CACHE_INDEX_KEY, 0, overflow - 1)
        if not stale_keys:
            return

        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.delete(*stale_keys)
            await pipe.zrem(EMBED_CACHE_INDEX_KEY, *stale_keys)
            await pipe.execute()

    async def _acquire_cache_lock(self, lock_key: str) -> str | None:
        """尝试获取 embedding 单飞锁，避免热点文本缓存击穿。"""
        if self.redis is None:
            return None
        token = str(uuid4())
        acquired = await self.redis.set(
            lock_key,
            token,
            ex=EMBED_CACHE_LOCK_TTL_SECONDS,
            nx=True,
        )
        return token if acquired else None

    async def _release_cache_lock(self, lock_key: str, token: str) -> None:
        """仅在仍持有锁时释放 embedding 单飞锁，避免误删他人锁。"""
        if self.redis is None:
            return
        try:
            current_value = await self.redis.get(lock_key)
            if current_value is None:
                return
            normalized_value = current_value.decode("utf-8") if isinstance(current_value, bytes) else str(current_value)
            if normalized_value == token:
                await self.redis.delete(lock_key)
        except Exception:
            logger.warning("释放 embedding 单飞锁失败 lock_key=%s", lock_key, exc_info=True)

    async def _wait_for_cached_embedding(
        self,
        *,
        cache_key: str,
        expected_signature: str,
    ) -> list[float] | None:
        """等待其他并发请求写入热缓存，减少相同文本重复打上游。"""
        if self.redis is None:
            return None
        deadline = time.perf_counter() + EMBED_CACHE_LOCK_WAIT_SECONDS
        while time.perf_counter() < deadline:
            await asyncio.sleep(EMBED_CACHE_LOCK_POLL_SECONDS)
            cached = await self.redis.get(cache_key)
            if not cached:
                continue
            payload = json.loads(cached)
            cached_signature = str(payload.get("cache_signature") or "").strip()
            if cached_signature and cached_signature != expected_signature:
                return None
            embedding = [float(item) for item in list(payload.get("embedding") or [])]
            if embedding:
                return embedding
        return None

    async def _upsert_vectors(
        self,
        vector_rows: Iterable[dict[str, Any]],
        *,
        index_dimension: int | None,
    ) -> None:
        """批量 upsert PGVector 本地索引。"""
        rows = list(vector_rows)
        if not rows:
            return
        started_at = time.perf_counter()
        logger.info(
            "[VectorizeTask] 开始写入向量索引: row_count=%s, index_dimension=%s, fallback_dimension=%s",
            len(rows),
            index_dimension,
            int(rows[0]["embedding_dimension"]),
        )
        vector_cast_type = build_vector_cast_type(
            index_dimension=index_dimension,
            fallback_dimension=int(rows[0]["embedding_dimension"]),
        )
        stmt = text(
            f"""
            INSERT INTO pg_chunk_search_unit_vectors (
                tenant_id,
                kb_id,
                search_unit_id,
                model_id,
                model_name,
                vector_scope,
                embedding_dimension,
                embedding,
                content_hash,
                is_active,
                metadata
            )
            VALUES (
                CAST(:tenant_id AS uuid),
                CAST(:kb_id AS uuid),
                :search_unit_id,
                CAST(:model_id AS uuid),
                :model_name,
                :vector_scope,
                :embedding_dimension,
                CAST(:embedding AS {vector_cast_type}),
                :content_hash,
                true,
                CAST(:metadata AS jsonb)
            )
            ON CONFLICT (search_unit_id, model_id, vector_scope)
            DO UPDATE SET
                model_name = EXCLUDED.model_name,
                embedding_dimension = EXCLUDED.embedding_dimension,
                embedding = EXCLUDED.embedding,
                content_hash = EXCLUDED.content_hash,
                is_active = true,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            """
        )
        for batch_start in range(0, len(rows), VECTOR_UPSERT_BATCH_SIZE):
            batch_rows = rows[batch_start: batch_start + VECTOR_UPSERT_BATCH_SIZE]
            batch_end = batch_start + len(batch_rows)
            logger.info(
                "[VectorizeTask] 开始写入向量索引批次: batch_range=%s-%s/%s, batch_size=%s",
                batch_start + 1,
                batch_end,
                len(rows),
                len(batch_rows),
            )
            # 不再回退到一次性 executemany，避免重现此前的卡住问题。
            # 小批量逐条执行可以兼顾稳定性与大批量场景下的可观测性。
            for row in batch_rows:
                await self.session.execute(stmt, row)
            logger.info(
                "[VectorizeTask] 向量索引批次写入完成: batch_range=%s-%s/%s",
                batch_start + 1,
                batch_end,
                len(rows),
            )
        await self.session.flush()
        logger.info(
            "[VectorizeTask] 向量索引写入完成: row_count=%s, elapsed_ms=%s",
            len(rows),
            int((time.perf_counter() - started_at) * 1000),
        )

    def _validate_embedding_dimension(
        self,
        model_snapshot: EmbeddingModelSnapshot,
        *,
        actual_dimension: int,
        index_dimension: int | None,
    ) -> None:
        """校验向量维度与当前 PGVector 表能力是否兼容。"""
        if actual_dimension <= 0:
            raise RuntimeError(f"Embedding 维度无效（{actual_dimension}）")
        expected_dimension = model_snapshot.embedding_dimension
        if expected_dimension is not None and actual_dimension != int(expected_dimension):
            raise RuntimeError(
                f"Embedding 维度不匹配，模型配置为 {expected_dimension}，实际返回 {actual_dimension}"
            )
        ensure_pgvector_dimension_compatible(
            actual_dimension=actual_dimension,
            index_dimension=index_dimension,
            scene="向量索引写入",
        )

    async def _ensure_model_embedding_dimension(
        self,
        model_snapshot: EmbeddingModelSnapshot,
        *,
        actual_dimension: int,
    ) -> None:
        """首次拿到真实向量后回填模型维度，避免依赖固定默认值。"""
        if actual_dimension <= 0:
            raise RuntimeError(f"Embedding 维度无效（{actual_dimension}）")
        if model_snapshot.embedding_dimension is not None:
            return

        model_snapshot.embedding_dimension = int(actual_dimension)
        # 使用运行时真实维度回填平台模型，后续训练与检索共享同一配置来源。
        stmt = text(
            """
            UPDATE platform_models
            SET
                embedding_dimension = :embedding_dimension,
                updated_at = CURRENT_TIMESTAMP
            WHERE
                id = CAST(:platform_model_id AS uuid)
                AND (embedding_dimension IS NULL OR embedding_dimension <= 0)
            """
        )
        await self.session.execute(
            stmt,
            {
                "platform_model_id": str(model_snapshot.platform_model_id),
                "embedding_dimension": int(actual_dimension),
            },
        )
        await self.session.flush()

    def _build_cache_signature(
        self,
        *,
        tenant_model: TenantModel,
        platform_model: PlatformModel,
        tenant_provider: TenantModelProvider,
    ) -> str:
        """构造 embedding 运行时签名，确保模型路由或默认参数变更后自动失效旧缓存。"""
        payload = {
            "raw_model_name": str(platform_model.raw_model_name or "").strip(),
            "provider_base_url": str(tenant_provider.base_url or "").strip(),
            "provider_api_version": str(tenant_provider.api_version or "").strip(),
            "provider_region": str(tenant_provider.region or "").strip(),
            "provider_adapter_override_type": str(tenant_provider.adapter_override_type or "").strip(),
            "provider_request_defaults": tenant_provider.request_defaults or {},
            "embedding_capability_base_url": str((tenant_provider.capability_base_urls or {}).get("embedding") or "").strip(),
            "embedding_capability_override": dict((tenant_provider.capability_overrides or {}).get("embedding") or {}),
            "tenant_model_adapter_override_type": str(tenant_model.adapter_override_type or "").strip(),
            "tenant_model_implementation_key_override": str(tenant_model.implementation_key_override or "").strip(),
            "tenant_model_request_schema_override": str(tenant_model.request_schema_override or "").strip(),
            "tenant_model_endpoint_path_override": str(tenant_model.endpoint_path_override or "").strip(),
            "tenant_model_request_defaults": tenant_model.request_defaults or {},
            "tenant_model_runtime_config": tenant_model.model_runtime_config or {},
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _build_cache_key(self, tenant_model_id: UUID, cache_signature: str, text: str) -> str:
        """构造 embedding 缓存键。"""
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{EMBED_CACHE_NAMESPACE}:{EMBED_CACHE_VERSION}:{tenant_model_id}:{cache_signature}:{digest}"

    def _build_cache_lock_key(self, cache_key: str) -> str:
        """从缓存键派生单飞锁键，避免不同文本或不同模型相互影响。"""
        return f"{EMBED_CACHE_LOCK_NAMESPACE}:{hashlib.sha256(cache_key.encode('utf-8')).hexdigest()}"

    def _should_use_cache(self, text: str) -> bool:
        """判断当前文本是否允许进入热缓存。"""
        if not settings.RAG_EMBED_CACHE_ENABLED:
            return False
        return 0 < len(text) <= settings.RAG_EMBED_CACHE_MAX_TEXT_LENGTH

    def _format_vector_literal(self, embedding: list[float]) -> str:
        """将向量格式化为 PostgreSQL vector 字面量。"""
        return "[" + ",".join(self._normalize_float(item) for item in embedding) + "]"

    def _normalize_float(self, value: float) -> str:
        """规整浮点数字面量，避免无效值写入。"""
        number = float(value)
        if number != number:
            raise RuntimeError("Embedding 返回 NaN，无法写入向量索引")
        if number == float("inf") or number == float("-inf"):
            raise RuntimeError("Embedding 返回无穷大，无法写入向量索引")
        return format(number, ".12g")
