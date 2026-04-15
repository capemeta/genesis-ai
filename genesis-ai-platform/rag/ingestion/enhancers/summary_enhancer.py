"""
摘要生成增强器
"""

import json
from typing import Dict, Any
from .base import BaseEnhancer
from .quality_utils import is_low_value_summary, strip_json_fence
from rag.llm import LLMExecutor, LLMRequest


class SummaryEnhancer(BaseEnhancer):
    """
    摘要生成增强器
    
    功能：
    - 生成分块摘要
    - 提升检索效果
    
    TODO: 集成 LLM 缓存
    """
    
    def __init__(self, max_length: int = 100, **kwargs):
        """
        初始化摘要生成器
        
        Args:
            max_length: 摘要最大长度
        """
        super().__init__(**kwargs)
        self.max_length = max_length
        self.executor = LLMExecutor(session_maker=kwargs.get("llm_session_maker"))
    
    async def enhance(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成摘要。
        """
        text = chunk["text"]
        request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是知识库分块摘要助手。"
                        "必须严格基于原文证据生成结果，不得编造。"
                        "请严格输出 JSON，不要输出解释、Markdown、代码块或额外前后缀。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"请为下面的分块内容生成一个不超过 {self.max_length} 字的摘要。\n"
                        "要求：\n"
                        "1. 只输出 JSON\n"
                        "2. JSON 格式必须为 {\"summary\": \"...\"}\n"
                        "3. 摘要要保留关键主题和实体\n"
                        "4. 不要编造原文没有的信息\n\n"
                        "5. 如果原文主要是标题、导航、模板话术、碎片句、字段名堆叠或信息密度过低，返回空字符串\n"
                        "6. 如果只能得到“本文介绍了”这类低信息摘要，返回空字符串\n\n"
                        f"分块内容：\n{text}"
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=256,
            request_source="kb_auto_summary",
            workload_type="batch_llm_enhance",
            tenant_id=str(chunk.get("tenant_id") or "") or None,
            kb_id=str(chunk.get("kb_id") or "") or None,
            kb_doc_id=str(chunk.get("kb_doc_id") or "") or None,
        )
        response = await self.executor.chat(request)
        summary = self._parse_summary(response.content)
        
        # 摘要主字段统一落顶层，metadata 中保留 enhancement 副本便于调试
        metadata = dict(chunk.get("metadata") or {})
        enhancement = dict(metadata.get("enhancement") or {})
        if summary:
            enhancement["summary"] = summary
            chunk["summary"] = summary
        else:
            enhancement.pop("summary", None)
            chunk.pop("summary", None)
        metadata["enhancement"] = enhancement
        chunk["metadata"] = metadata
        
        print(f"[SummaryEnhancer] 摘要生成完成: {summary[:50]}...")
        
        return chunk
    
    def _parse_summary(self, raw_text: str) -> str:
        """解析 LLM 输出的摘要 JSON。"""
        normalized = strip_json_fence(raw_text)
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"摘要增强结果不是合法 JSON: {raw_text[:200]}") from exc
        summary = str(payload.get("summary") or "").strip()
        if is_low_value_summary(summary):
            return ""
        return summary[: self.max_length]
