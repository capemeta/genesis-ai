"""
RAG 模块

提供完整的 RAG 功能：数据接入、向量化、检索、生成
"""

from .enums import (
    ChunkStrategy,
    DocumentStatus,
    ParseStrategy,
    SearchStrategy,
    TaskType,
)
from typing import Any


def __getattr__(name: str) -> Any:
    """按需加载重型 ingestion 工厂，避免导入 lexical 等轻量模块时初始化全链路依赖。"""

    if name in {"ParserFactory", "ChunkerFactory", "EnhancerFactory"}:
        from .ingestion import ChunkerFactory, EnhancerFactory, ParserFactory

        factories = {
            "ParserFactory": ParserFactory,
            "ChunkerFactory": ChunkerFactory,
            "EnhancerFactory": EnhancerFactory,
        }
        return factories[name]
    raise AttributeError(f"module 'rag' has no attribute {name!r}")

__all__ = [
    "DocumentStatus",
    "TaskType",
    "ParseStrategy",
    "ChunkStrategy",
    "SearchStrategy",
    "ParserFactory",
    "ChunkerFactory",
    "EnhancerFactory",
]
