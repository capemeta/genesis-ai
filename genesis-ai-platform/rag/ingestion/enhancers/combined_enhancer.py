"""
统一分块增强器。

职责：
- 通过一次 LLM 调用同时生成 summary / keywords / questions
- 按 selector 决策仅输出当前启用的能力
- 统一落库到 chunk.summary 与 metadata.enhancement
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .base import BaseEnhancer
from .quality_utils import is_low_value_summary, normalize_keywords, normalize_questions, strip_json_fence
from rag.llm import LLMExecutor, LLMRequest


class CombinedEnhancer(BaseEnhancer):
    """统一增强器，减少同一 chunk 的重复模型调用。"""

    def __init__(
        self,
        *,
        enable_summary: bool = False,
        enable_keywords: bool = False,
        enable_questions: bool = False,
        summary_max_length: int = 100,
        keyword_topn: int = 5,
        question_topn: int = 3,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.enable_summary = bool(enable_summary)
        self.enable_keywords = bool(enable_keywords)
        self.enable_questions = bool(enable_questions)
        self.summary_max_length = max(20, min(int(summary_max_length), 500))
        self.keyword_topn = max(1, min(int(keyword_topn), 20))
        self.question_topn = max(1, min(int(question_topn), 20))
        self.executor = LLMExecutor(session_maker=kwargs.get("llm_session_maker"))

    async def enhance(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """统一执行增强并写回 chunk。"""
        if not any([self.enable_summary, self.enable_keywords, self.enable_questions]):
            return chunk

        text = str(chunk.get("text") or chunk.get("content") or "").strip()
        if not text:
            return chunk

        request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是知识库分块语义增强助手。"
                        "你的任务是基于分块原文生成 summary、keywords、questions 等检索增强字段。"
                        "必须严格遵循原文证据，不得补充原文未明确表达的信息。"
                        "必须严格输出一个 JSON 对象，不要输出解释、Markdown、代码块或额外前后缀。"
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_user_prompt(text),
                },
            ],
            temperature=0.1,
            max_tokens=512,
            request_source="kb_chunk_enhancement",
            workload_type="batch_llm_enhance",
            tenant_id=str(chunk.get("tenant_id") or "") or None,
            kb_id=str(chunk.get("kb_id") or "") or None,
            kb_doc_id=str(chunk.get("kb_doc_id") or "") or None,
        )
        response = await self.executor.chat(request)
        payload = self._parse_payload(response.content)

        metadata = dict(chunk.get("metadata") or {})
        enhancement = dict(metadata.get("enhancement") or {})

        if self.enable_summary:
            summary = self._normalize_summary(payload.get("summary"))
            if summary:
                enhancement["summary"] = summary
                chunk["summary"] = summary
            else:
                enhancement.pop("summary", None)
                chunk.pop("summary", None)

        if self.enable_keywords:
            keywords = self._normalize_keywords(payload.get("keywords"))
            if keywords:
                enhancement["keywords"] = keywords
            else:
                enhancement.pop("keywords", None)

        if self.enable_questions:
            questions = self._normalize_questions(payload.get("questions"))
            if questions:
                enhancement["questions"] = questions
            else:
                enhancement.pop("questions", None)

        metadata["enhancement"] = enhancement
        chunk["metadata"] = metadata
        return chunk

    def _build_user_prompt(self, text: str) -> str:
        """构造统一增强 prompt。"""
        capability_lines: List[str] = []
        if self.enable_summary:
            capability_lines.append(
                f'- summary: 生成不超过 {self.summary_max_length} 字的摘要，保留主题、实体、结论或关键动作，不要抄整段原文；如果原文信息密度过低或缺乏稳定主题，返回空字符串'
            )
        if self.enable_keywords:
            capability_lines.append(
                f'- keywords: 提取最多 {self.keyword_topn} 个最有检索价值的关键词或短语，优先保留实体名、专业术语、产品名、模块名、指标名、主题词，不重复；如果没有高价值关键词，返回空数组'
            )
        if self.enable_questions:
            capability_lines.append(
                f'- questions: 生成最多 {self.question_topn} 个自然、简洁、适合作为检索问句的问题，问题应能仅依据本分块获得答案；如果无法形成高质量检索问句，返回空数组'
            )

        output_shape: dict[str, Any] = {
            "summary": "" if self.enable_summary else None,
            "keywords": [] if self.enable_keywords else None,
            "questions": [] if self.enable_questions else None,
        }

        return (
            "请根据下面的分块内容生成检索增强结果。\n"
            "目标：提升后续检索召回、关键词匹配与问句匹配效果。\n"
            "总规则：\n"
            "1. 只输出一个 JSON 对象\n"
            "2. 禁止输出任何解释、前后缀、Markdown 或代码块\n"
            "3. 所有内容必须严格基于原文证据，不要编造、延伸、脑补或补全原文没有的信息\n"
            "4. 输出语言必须与原文主语言保持一致；原文中必要的英文术语、代码标识符、产品名可保留原样\n"
            "5. 未启用的字段输出 null 或空数组\n"
            "6. 关键词和问题不要重复，也不要输出语义几乎相同的改写版本\n"
            "7. 若原文信息不足以支撑某个字段，summary 输出空字符串，对应列表输出空数组\n\n"
            "宁缺毋滥规则：\n"
            "1. 如果原文主要是标题、导航、模板话术、碎片句、字段名堆叠、噪声文本、无上下文短句，或信息密度过低，不要勉强生成内容\n"
            "2. 如果提取结果只有泛词、空话、套话、极弱检索价值的表述，则宁可返回空，不要为了凑数量输出低质量结果\n"
            "3. 如果某个问题无法仅根据本分块获得相对完整答案，就不要生成该问题\n\n"
            "本次启用能力：\n"
            f"{chr(10).join(capability_lines)}\n\n"
            "字段细则：\n"
            "1. summary：聚焦主题、对象、动作、结论或约束，避免空话，避免“本文介绍了”这类低信息表述；没有稳定主题时返回空字符串\n"
            "2. keywords：优先输出便于检索召回的名词或短语，不要输出“介绍”“说明”“相关内容”等泛词，不要整句，不要编号\n"
            "3. questions：必须是用户真实可能搜索的问题，尽量补足主语与关键对象，避免“它是什么”“如何处理这个问题”这类脱离上下文的代词问法；没有明确问点时返回空数组\n"
            "4. questions：问题之间应覆盖不同信息点，避免只是改几个字的重复问句\n\n"
            "输出 JSON 结构示例：\n"
            f"{json.dumps(output_shape, ensure_ascii=False)}\n\n"
            "分块内容如下，请仅基于这段内容完成任务：\n"
            "<<<CHUNK>>>\n"
            f"{text}"
            "\n<<<END_CHUNK>>>"
        )

    def _parse_payload(self, raw_text: str) -> Dict[str, Any]:
        """解析统一增强结果，兼容裸 JSON 与代码块 JSON。"""
        normalized = strip_json_fence(raw_text)
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError:
            start = normalized.find("{")
            end = normalized.rfind("}")
            if start < 0 or end <= start:
                raise RuntimeError(f"增强结果不是合法 JSON: {raw_text[:300]}")
            try:
                payload = json.loads(normalized[start : end + 1])
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"增强结果不是合法 JSON: {raw_text[:300]}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("增强结果格式非法，顶层必须为 JSON 对象")
        return payload

    def _normalize_summary(self, value: Any) -> str:
        """规范化摘要结果。"""
        summary = str(value or "").strip()
        if is_low_value_summary(summary):
            return ""
        return summary[: self.summary_max_length]

    def _normalize_list(self, value: Any, *, limit: int) -> List[str]:
        """规范化列表结果并去重。"""
        normalized: List[str] = []
        seen: set[str] = set()
        for item in list(value or []):
            text = str(item or "").strip()
            if not text:
                continue
            dedupe_key = text.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(text)
            if len(normalized) >= limit:
                break
        return normalized

    def _normalize_keywords(self, value: Any) -> List[str]:
        """规范化关键词，尽量过滤低价值或明显异常的候选项。"""
        normalized = self._normalize_list(value, limit=self.keyword_topn * 2)
        return normalize_keywords(normalized, limit=self.keyword_topn)

    def _normalize_questions(self, value: Any) -> List[str]:
        """规范化问题，补齐问号并过滤低质量问句。"""
        normalized = self._normalize_list(value, limit=self.question_topn * 2)
        return normalize_questions(normalized, limit=self.question_topn)
