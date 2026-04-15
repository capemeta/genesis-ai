"""
pgvector 结构辅助工具。

职责：
- 统一读取 pg_chunk_search_unit_vectors 的 embedding 列维度定义
- 在检索与向量化前做维度兼容性校验
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_VECTOR_DIMENSION_PATTERN = re.compile(r"vector\((\d+)\)", re.IGNORECASE)


def parse_vector_dimension(type_label: str | None) -> int | None:
    """从 PostgreSQL 类型描述中解析 vector 固定维度。"""
    normalized = str(type_label or "").strip()
    if not normalized:
        return None
    matched = _VECTOR_DIMENSION_PATTERN.fullmatch(normalized)
    if matched is None:
        return None
    return int(matched.group(1))


async def get_pgvector_embedding_dimension(session: AsyncSession) -> int | None:
    """读取向量索引表 embedding 列的固定维度。"""
    stmt = text(
        """
        SELECT format_type(a.atttypid, a.atttypmod) AS embedding_type
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE
            c.relname = 'pg_chunk_search_unit_vectors'
            AND a.attname = 'embedding'
            AND a.attnum > 0
            AND NOT a.attisdropped
        """
    )
    result = await session.execute(stmt)
    row = result.mappings().one_or_none()
    if row is None:
        raise RuntimeError("未找到 pg_chunk_search_unit_vectors.embedding 列，请检查数据库结构")
    return parse_vector_dimension(row.get("embedding_type"))


def ensure_pgvector_dimension_compatible(
    *,
    actual_dimension: int,
    index_dimension: int | None,
    scene: str,
) -> None:
    """校验当前向量维度是否与 pgvector 列定义兼容。"""
    if actual_dimension <= 0:
        raise RuntimeError(f"{scene}失败：embedding 维度无效（{actual_dimension}）")
    if index_dimension is None:
        return
    if actual_dimension != index_dimension:
        raise RuntimeError(
            f"{scene}失败：当前 embedding 实际为 {actual_dimension} 维，"
            f"但 pg_chunk_search_unit_vectors.embedding 列固定为 {index_dimension} 维。"
            "请统一知识库 embedding 模型维度与向量表结构后重新构建索引。"
        )


def build_vector_cast_type(*, index_dimension: int | None, fallback_dimension: int) -> str:
    """构造 SQL 中使用的 vector cast 类型。"""
    if index_dimension is not None:
        return f"vector({index_dimension})"
    return f"vector({max(1, int(fallback_dimension))})"
