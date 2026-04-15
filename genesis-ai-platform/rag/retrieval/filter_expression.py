"""检索硬过滤表达式工具。

表达式用于 API 显式硬过滤，支持 AND / OR / NOT 与括号语义。
"""

from __future__ import annotations

import re
from typing import Any, Mapping


EXPRESSION_LOGICAL_OPS = {"and", "or", "not"}
EXPRESSION_COMPARE_OPS = {"eq", "ne", "in", "not_in", "exists", "not_exists"}


def serialize_filter_value(value: Any) -> str:
    """统一 JSON/metadata 文本比较口径。"""

    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def normalize_filter_expression(raw_expression: Any, *, max_depth: int = 8) -> dict[str, Any]:
    """把 API 传入的表达式规整为稳定结构，非法部分直接丢弃。"""

    if not isinstance(raw_expression, Mapping):
        return {}

    def _normalize_node(node: Any, depth: int) -> dict[str, Any]:
        if depth > max_depth or not isinstance(node, Mapping):
            return {}

        raw_op = str(node.get("op") or node.get("operator") or "").strip().lower()
        if raw_op in EXPRESSION_LOGICAL_OPS:
            raw_items = node.get("items")
            if raw_items is None:
                raw_items = node.get("clauses")
            if raw_items is None:
                raw_items = [node.get("item")]
            normalized_items = [
                item
                for item in (_normalize_node(raw_item, depth + 1) for raw_item in list(raw_items or []))
                if item
            ]
            if raw_op == "not":
                return {"op": "not", "items": normalized_items[:1]} if normalized_items else {}
            if not normalized_items:
                return {}
            if len(normalized_items) == 1:
                return normalized_items[0]
            return {"op": raw_op, "items": normalized_items[:32]}

        field = str(node.get("field") or node.get("type") or node.get("target") or "").strip()
        compare_op = raw_op if raw_op in EXPRESSION_COMPARE_OPS else str(node.get("match") or "in").strip().lower()
        if compare_op not in EXPRESSION_COMPARE_OPS:
            compare_op = "in"
        path = _normalize_path(node.get("path") if node.get("path") is not None else node.get("key"))
        values = _normalize_values(node.get("values") if node.get("values") is not None else node.get("value"))

        if compare_op not in {"exists", "not_exists"} and not values:
            return {}
        if field in {"metadata", "document_metadata", "search_unit_metadata"} and not path:
            return {}
        return {
            "field": field,
            "op": compare_op,
            "path": path,
            "values": values[:64],
        }

    return _normalize_node(raw_expression, 0)


def filter_expression_has_field(expression: Mapping[str, Any] | None, fields: set[str]) -> bool:
    """判断表达式树中是否包含某类字段。"""

    if not isinstance(expression, Mapping) or not expression:
        return False
    op = str(expression.get("op") or "").strip().lower()
    if op in EXPRESSION_LOGICAL_OPS:
        return any(filter_expression_has_field(item, fields) for item in list(expression.get("items") or []))
    return str(expression.get("field") or "").strip() in fields


def build_jsonb_expression_sql(
    *,
    expression: Mapping[str, Any],
    json_column: str,
    params: dict[str, Any],
    prefix: str,
) -> str:
    """生成 search unit JSONB 表达式 SQL 条件。"""

    counter = {"value": 0}

    def _next_param(name: str) -> str:
        counter["value"] += 1
        return f"{prefix}_{name}_{counter['value']}"

    def _node_sql(node: Mapping[str, Any]) -> str:
        op = str(node.get("op") or "").strip().lower()
        if op in {"and", "or"}:
            parts = [_node_sql(item) for item in list(node.get("items") or []) if isinstance(item, Mapping)]
            parts = [item for item in parts if item]
            if not parts:
                return ""
            joiner = " AND " if op == "and" else " OR "
            return "(" + joiner.join(parts) + ")"
        if op == "not":
            items = [item for item in list(node.get("items") or []) if isinstance(item, Mapping)]
            if not items:
                return ""
            child = _node_sql(items[0])
            return f"(NOT {child})" if child else ""

        field = str(node.get("field") or "").strip()
        if field not in {"search_unit_metadata", "metadata"}:
            return ""
        path = [str(item).strip() for item in list(node.get("path") or []) if str(item).strip()]
        if not path:
            return ""
        path_param = _next_param("path")
        params[path_param] = path
        value_expr = f"({json_column} #>> CAST(:{path_param} AS text[]))"
        values = [serialize_filter_value(item) for item in list(node.get("values") or [])]

        if op == "exists":
            return f"({value_expr} IS NOT NULL)"
        if op == "not_exists":
            return f"({value_expr} IS NULL)"

        if op == "eq":
            value_param = _next_param("value")
            params[value_param] = values[0] if values else ""
            return f"({value_expr} = :{value_param})"
        if op == "ne":
            value_param = _next_param("value")
            params[value_param] = values[0] if values else ""
            return f"({value_expr} IS NULL OR {value_expr} <> :{value_param})"
        value_param = _next_param("values")
        params[value_param] = values
        if op == "not_in":
            return f"({value_expr} IS NULL OR {value_expr} NOT IN :{value_param})"
        return f"({value_expr} IN :{value_param})"

    sql = _node_sql(expression)
    return sql


def build_search_unit_expression_sql(
    *,
    expression: Mapping[str, Any],
    params: dict[str, Any],
    prefix: str,
) -> str:
    """生成召回后端可执行的完整表达式 SQL。"""

    counter = {"value": 0}

    def _next_param(name: str) -> str:
        counter["value"] += 1
        return f"{prefix}_{name}_{counter['value']}"

    def _value_sql(value_expr: str, op: str, values: list[Any]) -> str:
        if op == "exists":
            return f"({value_expr} IS NOT NULL)"
        if op == "not_exists":
            return f"({value_expr} IS NULL)"
        serialized_values = [serialize_filter_value(item) for item in values]
        if op == "eq":
            value_param = _next_param("value")
            params[value_param] = serialized_values[0] if serialized_values else ""
            return f"({value_expr} = :{value_param})"
        if op == "ne":
            value_param = _next_param("value")
            params[value_param] = serialized_values[0] if serialized_values else ""
            return f"({value_expr} IS NULL OR {value_expr} <> :{value_param})"
        value_param = _next_param("values")
        params[value_param] = serialized_values
        if op == "not_in":
            return f"({value_expr} IS NULL OR {value_expr} NOT IN :{value_param})"
        return f"({value_expr} IN :{value_param})"

    def _uuid_sql(value_expr: str, op: str, values: list[Any]) -> str:
        serialized_values = [str(item).strip() for item in values if str(item).strip()]
        if op == "exists":
            return f"({value_expr} IS NOT NULL)"
        if op == "not_exists":
            return f"({value_expr} IS NULL)"
        if op == "eq":
            value_param = _next_param("value")
            params[value_param] = serialized_values[0] if serialized_values else ""
            return f"({value_expr} = :{value_param})"
        if op == "ne":
            value_param = _next_param("value")
            params[value_param] = serialized_values[0] if serialized_values else ""
            return f"({value_expr} IS NULL OR {value_expr} <> :{value_param})"
        value_param = _next_param("values")
        params[value_param] = serialized_values
        if op == "not_in":
            return f"({value_expr} IS NULL OR {value_expr} NOT IN :{value_param})"
        return f"({value_expr} IN :{value_param})" if serialized_values else "(false)"

    def _node_sql(node: Mapping[str, Any]) -> str:
        op = str(node.get("op") or "").strip().lower()
        if op in {"and", "or"}:
            parts = [_node_sql(item) for item in list(node.get("items") or []) if isinstance(item, Mapping)]
            parts = [item for item in parts if item]
            if not parts:
                return ""
            joiner = " AND " if op == "and" else " OR "
            return "(" + joiner.join(parts) + ")"
        if op == "not":
            items = [item for item in list(node.get("items") or []) if isinstance(item, Mapping)]
            if not items:
                return ""
            child = _node_sql(items[0])
            return f"(NOT {child})" if child else ""

        field = str(node.get("field") or "").strip()
        values = list(node.get("values") or [])
        if field in {"metadata", "document_metadata"}:
            path = [str(item).strip() for item in list(node.get("path") or []) if str(item).strip()]
            if not path:
                return ""
            path_param = _next_param("path")
            params[path_param] = path
            # 这里必须使用数据库真实列名 metadata，而不是 ORM 属性名 custom_metadata。
            return _value_sql(f"(kbd.metadata #>> CAST(:{path_param} AS text[]))", op, values)
        if field in {"search_unit_metadata"}:
            path = [str(item).strip() for item in list(node.get("path") or []) if str(item).strip()]
            if not path:
                return ""
            path_param = _next_param("path")
            params[path_param] = path
            return _value_sql(f"(su.metadata #>> CAST(:{path_param} AS text[]))", op, values)
        if field in {"folder", "folder_id"}:
            return _uuid_sql("CAST(kbd.folder_id AS text)", op, values)
        if field in {"kb_doc", "kb_doc_id"}:
            return _uuid_sql("CAST(kbd.id AS text)", op, values)
        if field in {"document", "document_id"}:
            return _uuid_sql("CAST(kbd.document_id AS text)", op, values)
        if field in {"tag", "doc_tag", "tag_id"}:
            value_param = _next_param("values")
            params[value_param] = [str(item).strip() for item in values if str(item).strip()]
            exists_sql = (
                "EXISTS (SELECT 1 FROM resource_tags rt "
                "WHERE rt.tenant_id = su.tenant_id AND rt.kb_id = su.kb_id "
                "AND rt.target_type = 'kb_doc' AND rt.action = 'add' "
                "AND rt.target_id = su.kb_doc_id AND CAST(rt.tag_id AS text) IN :"
                f"{value_param})"
            )
            if op == "exists":
                return f"({exists_sql})"
            if op in {"not_exists", "ne", "not_in"}:
                return f"(NOT {exists_sql})"
            return f"({exists_sql})" if params[value_param] else "(false)"
        return ""

    return _node_sql(expression)


def collect_expanding_param_names(expression_sql: str, prefix: str) -> list[str]:
    """收集表达式 SQL 中需要 expanding bindparam 的参数名。"""

    names = [
        f"{prefix}_values_{match}"
        for match in re.findall(rf"\b(?:IN|NOT IN)\s+:{re.escape(prefix)}_values_(\d+)\b", expression_sql)
    ]
    return list(dict.fromkeys(names))


def _normalize_path(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [item for item in text.split(".") if item]


def _normalize_values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if item is not None and item != ""]
    if value == "":
        return []
    return [value]
