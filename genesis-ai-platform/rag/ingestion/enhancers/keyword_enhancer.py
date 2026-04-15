"""
关键词提取增强器
"""

import json
from typing import Dict, Any, List
from .base import BaseEnhancer
from .quality_utils import normalize_keywords, strip_json_fence
from rag.llm import LLMExecutor, LLMRequest


class KeywordEnhancer(BaseEnhancer):
    """
    关键词提取增强器
    
    功能：
    - 提取关键词
    - 提升检索召回率
    
    TODO: 集成 LLM 缓存
    """
    
    def __init__(self, topn: int = 5, **kwargs):
        """
        初始化关键词提取器
        
        Args:
            topn: 提取关键词数量
        """
        super().__init__(**kwargs)
        self.topn = topn
        self.executor = LLMExecutor(session_maker=kwargs.get("llm_session_maker"))
    
    async def enhance(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取关键词。
        """
        text = chunk["text"]
        request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是知识库分块关键词增强助手。"
                        "必须严格基于原文证据生成结果，不得编造。"
                        "请严格输出 JSON，不要输出解释、Markdown、代码块或额外前后缀。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"请从下面的分块内容中提取 {self.topn} 个最有检索价值的关键词。\n"
                        "要求：\n"
                        "1. 只输出 JSON\n"
                        "2. JSON 格式必须为 {\"keywords\": [\"...\", \"...\"]}\n"
                        "3. 关键词尽量短，避免整句\n"
                        "4. 不要输出重复项\n"
                        f"5. 最多输出 {self.topn} 个\n"
                        "6. 优先保留实体名、专业术语、产品名、模块名、指标名、主题词\n"
                        "7. 如果原文信息密度过低，或只能提取出“介绍”“说明”“内容”这类泛词，返回空数组\n\n"
                        f"分块内容：\n{text}"
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=256,
            request_source="kb_auto_keywords",
            workload_type="batch_llm_enhance",
            tenant_id=str(chunk.get("tenant_id") or "") or None,
            kb_id=str(chunk.get("kb_id") or "") or None,
            kb_doc_id=str(chunk.get("kb_doc_id") or "") or None,
        )
        response = await self.executor.chat(request)
        keywords = self._parse_keywords(response.content)
        
        # 统一写入 enhancement 命名空间，避免与其他元数据字段混用
        metadata = dict(chunk.get("metadata") or {})
        enhancement = dict(metadata.get("enhancement") or {})
        if keywords:
            enhancement["keywords"] = keywords
        else:
            enhancement.pop("keywords", None)
        metadata["enhancement"] = enhancement
        chunk["metadata"] = metadata
        
        print(f"[KeywordEnhancer] 关键词提取完成: {keywords}")
        
        return chunk
    
    def _parse_keywords(self, raw_text: str) -> List[str]:
        """解析 LLM 输出的关键词 JSON。"""
        normalized = strip_json_fence(raw_text)
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"关键词增强结果不是合法 JSON: {raw_text[:200]}") from exc
        keywords = [str(item).strip() for item in list(payload.get("keywords") or []) if str(item).strip()]
        return normalize_keywords(keywords, limit=self.topn)
