"""
问题提取增强器
"""

import json
from typing import Dict, Any, List
from .base import BaseEnhancer
from .quality_utils import normalize_questions, strip_json_fence
from rag.llm import LLMExecutor, LLMRequest


class QuestionEnhancer(BaseEnhancer):
    """
    问题提取增强器
    
    功能：
    - 提取可能的问题
    - 支持问答式检索
    
    TODO: 集成 LLM 缓存
    """
    
    def __init__(self, topn: int = 3, **kwargs):
        """
        初始化问题提取器
        
        Args:
            topn: 提取问题数量
        """
        super().__init__(**kwargs)
        self.topn = topn
        self.executor = LLMExecutor(session_maker=kwargs.get("llm_session_maker"))
    
    async def enhance(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取问题。
        """
        text = chunk["text"]
        request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是知识库检索问题增强助手。"
                        "必须严格基于原文证据生成结果，不得编造。"
                        "请严格输出 JSON，不要输出解释、Markdown、代码块或额外前后缀。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"请根据下面的分块内容，生成 {self.topn} 个用户可能会提出的检索问题。\n"
                        "要求：\n"
                        "1. 只输出 JSON\n"
                        "2. JSON 格式必须为 {\"questions\": [\"...\", \"...\"]}\n"
                        "3. 问题要自然、简洁、适合作为搜索问句\n"
                        "4. 问题之间不要重复\n"
                        f"5. 最多输出 {self.topn} 个\n"
                        "6. 问题应能仅依据当前分块获得答案\n"
                        "7. 如果没有明确问点，或只能生成“它是什么”这类弱问题，返回空数组\n\n"
                        f"分块内容：\n{text}"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=384,
            request_source="kb_auto_questions",
            workload_type="batch_llm_enhance",
            tenant_id=str(chunk.get("tenant_id") or "") or None,
            kb_id=str(chunk.get("kb_id") or "") or None,
            kb_doc_id=str(chunk.get("kb_doc_id") or "") or None,
        )
        response = await self.executor.chat(request)
        questions = self._parse_questions(response.content)
        
        # 统一写入 enhancement 命名空间，避免与其他元数据字段混用
        metadata = dict(chunk.get("metadata") or {})
        enhancement = dict(metadata.get("enhancement") or {})
        if questions:
            enhancement["questions"] = questions
        else:
            enhancement.pop("questions", None)
        metadata["enhancement"] = enhancement
        chunk["metadata"] = metadata
        
        print(f"[QuestionEnhancer] 问题提取完成: {questions}")
        
        return chunk
    
    def _parse_questions(self, raw_text: str) -> List[str]:
        """解析 LLM 输出的问题 JSON。"""
        normalized = strip_json_fence(raw_text)
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"问题增强结果不是合法 JSON: {raw_text[:200]}") from exc
        questions = [str(item).strip() for item in list(payload.get("questions") or []) if str(item).strip()]
        return normalize_questions(questions, limit=self.topn)
