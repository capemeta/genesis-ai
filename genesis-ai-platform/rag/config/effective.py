"""
RAG 生效配置解析。

设计目标：
- 将 effective_*_config 的合并逻辑从任务公共模块中拆出
- 统一知识库级、类型级、文档级三层配置解析
- 为后续 selector / executor / train / kg / raptor 提供稳定入口
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument


def _deep_merge_dict(base: Optional[Dict[str, Any]], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """深度合并字典，仅在两侧都是 dict 时递归合并。"""
    merged = dict(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged.get(key), value)
        else:
            merged[key] = value
    return merged


def _extract_kb_type_pipeline_overrides(kb: Optional[KnowledgeBase]) -> Dict[str, Any]:
    """
    从 retrieval_config 中提取知识库类型级 pipeline 覆盖。

    约定优先读取：
    1. retrieval_config[kb_type].pipeline
    2. retrieval_config[kb_type]
    """
    if kb is None:
        return {}

    retrieval_config = dict(kb.retrieval_config or {})
    kb_type = str(kb.type or "").strip()
    if not kb_type:
        return {}

    type_config = retrieval_config.get(kb_type)
    if not isinstance(type_config, dict):
        return {}

    pipeline_config = type_config.get("pipeline")
    if isinstance(pipeline_config, dict):
        return dict(pipeline_config)
    return dict(type_config)


def resolve_effective_pipeline_config(
    kb_doc: KnowledgeBaseDocument,
    *,
    kb: Optional[KnowledgeBase] = None,
) -> Dict[str, Any]:
    """
    统一解析任务链生效配置。

    优先级（高 -> 低）：
    - 文档级：knowledge_base_documents
    - 类型级：knowledge_bases.retrieval_config[type].pipeline
    - 知识库级：knowledge_bases
    """
    type_overrides = _extract_kb_type_pipeline_overrides(kb)

    # 知识库级默认配置
    global_chunking_mode = str(kb.chunking_mode or "smart") if kb else "smart"
    global_chunking_config = dict(kb.chunking_config or {}) if kb else {}
    global_parse_config: Dict[str, Any] = {}
    global_retrieval_config: Dict[str, Any] = dict(kb.retrieval_config or {}) if kb else {}
    global_intelligence_config: Dict[str, Any] = dict(kb.intelligence_config or {}) if kb else {}

    # 类型级覆盖
    type_chunking_mode = str(type_overrides.get("chunking_mode") or "").strip() or None
    type_parse_config = dict(type_overrides.get("parse_config") or {})
    type_chunking_config = dict(type_overrides.get("chunking_config") or {})
    type_intelligence_config = dict(type_overrides.get("intelligence_config") or {})

    # 文档级覆盖
    doc_parse_config = dict(kb_doc.parse_config or {})
    doc_chunking_config = dict(kb_doc.chunking_config or {})
    doc_intelligence_config = dict(kb_doc.intelligence_config or {})

    chunking_mode = (
        str(doc_chunking_config.get("chunking_mode") or "").strip()
        or type_chunking_mode
        or global_chunking_mode
        or "smart"
    )

    parse_config = _deep_merge_dict(
        _deep_merge_dict(global_parse_config, type_parse_config),
        doc_parse_config,
    )
    chunking_config = _deep_merge_dict(
        _deep_merge_dict(global_chunking_config, type_chunking_config),
        doc_chunking_config,
    )
    intelligence_config = _deep_merge_dict(
        _deep_merge_dict(global_intelligence_config, type_intelligence_config),
        doc_intelligence_config,
    )

    effective_enhancement_config = dict(intelligence_config.get("enhancement") or {})
    effective_kg_config = dict(intelligence_config.get("knowledge_graph") or {})
    effective_raptor_config = dict(intelligence_config.get("raptor") or {})

    return {
        "chunking_mode": chunking_mode,
        "parse_config": parse_config,
        "chunking_config": chunking_config,
        "retrieval_config": global_retrieval_config,
        "intelligence_config": intelligence_config,
        "effective_enhancement_config": effective_enhancement_config,
        "effective_kg_config": effective_kg_config,
        "effective_raptor_config": effective_raptor_config,
    }


def build_effective_config(
    kb_doc: KnowledgeBaseDocument,
    extra: Optional[Dict[str, Any]] = None,
    kb: Optional[KnowledgeBase] = None,
) -> Dict[str, Any]:
    """构造任务链实际生效配置快照。"""
    payload = resolve_effective_pipeline_config(kb_doc, kb=kb)
    if extra:
        payload.update(extra)
    return payload
