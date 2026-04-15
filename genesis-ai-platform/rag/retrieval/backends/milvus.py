"""
Milvus 检索后端骨架。
"""

from typing import List

from rag.lexical.analysis import get_default_lexical_analyzer
from rag.lexical.analysis.types import LexicalAnalyzerInput
from rag.retrieval.backends.base import LexicalSearchBackend, VectorSearchBackend
from rag.retrieval.types import LexicalSearchRequest, SearchHit, VectorSearchRequest


class MilvusVectorSearchBackend(VectorSearchBackend):
    """Milvus 向量检索后端骨架。"""

    backend_type = "milvus"

    async def search(self, request: VectorSearchRequest) -> List[SearchHit]:
        """执行 Milvus 向量检索。

        TODO:
        1. 建立 Milvus client
        2. 设计 collection / partition / scalar payload 映射
        3. 将结果转换成统一 `SearchHit`
        """
        raise NotImplementedError("Milvus 向量检索后端尚未实现")


class MilvusLexicalSearchBackend(LexicalSearchBackend):
    """Milvus 全文 / BM25 检索后端骨架。"""

    backend_type = "milvus_lexical"

    async def search(self, request: LexicalSearchRequest) -> List[SearchHit]:
        """执行 Milvus 全文检索。

        TODO:
        1. 配置 Milvus VARCHAR analyzer / BM25 Function，中文优先评估 jieba tokenizer
        2. 使用统一 `LexicalAnalyzer` 输出衔接 query expansion 与停用词
        3. 将 Milvus search 结果映射回统一 `SearchHit`
        """
        _analysis = get_default_lexical_analyzer().analyze(
            LexicalAnalyzerInput(
                text=request.query,
                mode="query",
                priority_terms=list(request.priority_terms or []),
                priority_phrases=list(request.priority_phrases or []),
                synonym_terms=list(request.synonym_terms or []),
                glossary_terms=list(request.glossary_terms or []),
                retrieval_stopwords=list(request.retrieval_stopwords or []),
            )
        )
        raise NotImplementedError("Milvus 全文检索后端尚未实现")
