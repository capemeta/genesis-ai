"""
QA Markdown 文本格式化工具。
"""

from typing import Iterable, List


def build_qa_markdown_text(
    *,
    question: str,
    answer: str,
    similar_questions: Iterable[str] | None = None,
    category: str | None = None,
    tags: Iterable[str] | None = None,
) -> str:
    """将结构化 QA 记录渲染为统一的 Markdown 文本。"""
    normalized_question = str(question or "").strip()
    normalized_answer = str(answer or "").strip()
    normalized_aliases: List[str] = [
        str(item).strip() for item in (similar_questions or []) if str(item).strip()
    ]
    normalized_category = str(category or "").strip()
    normalized_tags: List[str] = [str(item).strip() for item in (tags or []) if str(item).strip()]

    parts: List[str] = [
        "## 问题",
        normalized_question,
    ]

    if normalized_aliases:
        parts.extend(
            [
                "",
                "## 相似问题",
                *[f"- {item}" for item in normalized_aliases],
            ]
        )

    if normalized_category:
        parts.extend(
            [
                "",
                "## 分类",
                normalized_category,
            ]
        )

    if normalized_tags:
        parts.extend(
            [
                "",
                "## 标签",
                *[f"- {item}" for item in normalized_tags],
            ]
        )

    parts.extend(
        [
            "",
            "## 答案",
            normalized_answer,
        ]
    )
    return "\n".join(parts).strip()
