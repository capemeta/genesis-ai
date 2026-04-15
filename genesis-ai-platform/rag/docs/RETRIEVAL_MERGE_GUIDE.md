# 检索与传递分离实现指南

## 核心需求

**向量化时**：使用子块（table_1, table_2, table_3...）进行检索
**传递给 LLM**：使用完整的原始元素

## 实现方案

### 方案选择：检索后动态合并（推荐）

**优点**：
- 不需要修改数据库结构
- 存储高效（不冗余存储完整内容）
- 灵活性高，易于调整策略

### 实现步骤

#### 1. 在分块时添加元素标识

当前代码已经在 metadata 中包含了 `is_split`、`split_part`、`split_total` 等字段，我们需要添加一个唯一的元素 ID。

```python
# 在 _split_table、_split_code 等方法中添加
from uuid import uuid4

def _split_table(self, element, section, metadata):
    # ... 现有代码
    
    # 生成唯一的元素 ID
    original_element_id = str(uuid4())
    
    sub_tables = []
    for i in range(0, len(data_lines), rows_per_chunk):
        # ... 现有代码
        
        sub_tables.append({
            "text": sub_table_content,
            "metadata": {
                **metadata,
                # ... 现有字段
                "original_element_id": original_element_id,  # 新增
                "original_element_type": "table",            # 新增
            }
        })
    
    return sub_tables
```

#### 2. 在数据库中存储关联信息

在 `segments` 表中，metadata 字段（JSONB）已经可以存储这些信息，无需修改表结构。

#### 3. 实现检索合并逻辑

在 RAG 检索服务中实现合并逻辑：

```python
# rag/retrieval/merge_service.py

from typing import List, Dict, Set
from uuid import UUID

class RetrievalMergeService:
    """检索结果合并服务"""
    
    async def retrieve_and_merge(
        self,
        query_embedding: List[float],
        kb_id: UUID,
        tenant_id: UUID,
        top_k: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict]:
        """
        检索并合并拆分的元素
        
        流程：
        1. 向量检索（使用子块）
        2. 识别被拆分的元素
        3. 获取完整元素的所有子块
        4. 合并子块
        5. 返回合并后的结果
        """
        # 1. 向量检索（返回 top_k * 2，因为可能有拆分）
        raw_chunks = await self._vector_search(
            query_embedding=query_embedding,
            kb_id=kb_id,
            tenant_id=tenant_id,
            top_k=top_k * 2,
            similarity_threshold=similarity_threshold
        )
        
        # 2. 识别被拆分的元素
        split_element_ids = set()
        for chunk in raw_chunks:
            if chunk.metadata.get("is_split"):
                element_id = chunk.metadata.get("original_element_id")
                if element_id:
                    split_element_ids.add(element_id)
        
        # 3. 获取完整元素的所有子块
        element_chunks_map = {}
        if split_element_ids:
            element_chunks_map = await self._get_all_sub_chunks(
                element_ids=list(split_element_ids),
                kb_id=kb_id,
                tenant_id=tenant_id
            )
        
        # 4. 合并子块
        merged_chunks = []
        processed_element_ids = set()
        
        for chunk in raw_chunks:
            if chunk.metadata.get("is_split"):
                element_id = chunk.metadata.get("original_element_id")
                
                # 如果已经处理过这个元素，跳过
                if element_id in processed_element_ids:
                    continue
                
                # 合并所有子块
                all_sub_chunks = element_chunks_map.get(element_id, [])
                if all_sub_chunks:
                    merged_chunk = self._merge_sub_chunks(all_sub_chunks)
                    merged_chunks.append(merged_chunk)
                    processed_element_ids.add(element_id)
                else:
                    # 如果找不到其他子块，使用当前块
                    merged_chunks.append(chunk)
            else:
                # 未拆分的块，直接使用
                merged_chunks.append(chunk)
        
        # 5. 返回 top_k 个结果
        return merged_chunks[:top_k]
    
    async def _vector_search(
        self,
        query_embedding: List[float],
        kb_id: UUID,
        tenant_id: UUID,
        top_k: int,
        similarity_threshold: float
    ) -> List[Dict]:
        """向量检索（使用子块）"""
        from sqlalchemy import select, func
        from models.segment import Segment
        from models.embedding import Embedding
        from core.database.session import get_session
        
        async with get_session() as session:
            stmt = (
                select(
                    Segment,
                    Embedding,
                    (1 - func.cosine_distance(Embedding.embedding, query_embedding)).label("similarity")
                )
                .join(Embedding, Segment.id == Embedding.segment_id)
                .where(
                    Segment.tenant_id == tenant_id,
                    Segment.kb_id == kb_id,
                    Segment.deleted_at.is_(None)
                )
                .order_by(text("similarity DESC"))
                .limit(top_k)
            )
            
            result = await session.execute(stmt)
            rows = result.all()
            
            chunks = []
            for segment, embedding, similarity in rows:
                if similarity >= similarity_threshold:
                    chunks.append({
                        "id": segment.id,
                        "text": segment.content,
                        "metadata": segment.metadata,
                        "similarity": similarity,
                    })
            
            return chunks
    
    async def _get_all_sub_chunks(
        self,
        element_ids: List[str],
        kb_id: UUID,
        tenant_id: UUID
    ) -> Dict[str, List[Dict]]:
        """
        获取指定元素的所有子块
        
        Returns:
            Dict[element_id, List[chunk]]
        """
        from sqlalchemy import select
        from models.segment import Segment
        from core.database.session import get_session
        
        async with get_session() as session:
            # 使用 JSONB 查询
            stmt = select(Segment).where(
                Segment.tenant_id == tenant_id,
                Segment.kb_id == kb_id,
                Segment.deleted_at.is_(None),
                Segment.metadata['original_element_id'].astext.in_(element_ids)
            )
            
            result = await session.execute(stmt)
            segments = result.scalars().all()
            
            # 按 element_id 分组
            element_chunks_map = {}
            for segment in segments:
                element_id = segment.metadata.get("original_element_id")
                if element_id:
                    if element_id not in element_chunks_map:
                        element_chunks_map[element_id] = []
                    
                    element_chunks_map[element_id].append({
                        "id": segment.id,
                        "text": segment.content,
                        "metadata": segment.metadata,
                        "split_part": segment.metadata.get("split_part", 1),
                    })
            
            # 按 split_part 排序
            for element_id in element_chunks_map:
                element_chunks_map[element_id].sort(key=lambda x: x["split_part"])
            
            return element_chunks_map
    
    def _merge_sub_chunks(self, sub_chunks: List[Dict]) -> Dict:
        """
        合并子块
        
        策略：
        - 表格：合并所有行（去重表头）
        - 代码：合并所有代码（去重注释）
        - 列表：合并所有列表项
        - 其他：简单拼接
        """
        if not sub_chunks:
            return {}
        
        # 获取元素类型
        element_type = sub_chunks[0]["metadata"].get("element_type", "text")
        
        if element_type == "table":
            return self._merge_table_chunks(sub_chunks)
        elif element_type == "code":
            return self._merge_code_chunks(sub_chunks)
        elif element_type == "list":
            return self._merge_list_chunks(sub_chunks)
        else:
            return self._merge_generic_chunks(sub_chunks)
    
    def _merge_table_chunks(self, sub_chunks: List[Dict]) -> Dict:
        """合并表格子块"""
        # 提取表头（从第一个子块）
        first_chunk_text = sub_chunks[0]["text"]
        lines = first_chunk_text.split('\n')
        header_line = lines[0]
        separator_line = lines[1]
        
        # 收集所有数据行（跳过表头）
        all_data_rows = []
        for chunk in sub_chunks:
            chunk_lines = chunk["text"].split('\n')
            data_rows = chunk_lines[2:]  # 跳过表头和分隔符
            all_data_rows.extend(data_rows)
        
        # 合并
        merged_text = '\n'.join([header_line, separator_line] + all_data_rows)
        
        # 使用第一个子块的 metadata，但标记为已合并
        merged_metadata = sub_chunks[0]["metadata"].copy()
        merged_metadata["is_merged"] = True
        merged_metadata["merged_from_parts"] = len(sub_chunks)
        
        return {
            "id": sub_chunks[0]["id"],  # 使用第一个子块的 ID
            "text": merged_text,
            "metadata": merged_metadata,
            "similarity": sub_chunks[0].get("similarity", 0),  # 使用第一个子块的相似度
        }
    
    def _merge_code_chunks(self, sub_chunks: List[Dict]) -> Dict:
        """合并代码子块"""
        # 提取语言标记
        first_chunk_text = sub_chunks[0]["text"]
        first_line = first_chunk_text.split('\n')[0]
        language = first_line.replace('```', '').strip()
        
        # 收集所有代码行
        all_code_lines = []
        for chunk in sub_chunks:
            chunk_lines = chunk["text"].split('\n')
            code_lines = chunk_lines[1:-1]  # 去掉 ``` 标记
            
            # 去掉 "# ... 接上文" 注释
            filtered_lines = [line for line in code_lines if not line.strip().startswith('# ... 接上文')]
            all_code_lines.extend(filtered_lines)
        
        # 合并
        merged_text = f"```{language}\n" + '\n'.join(all_code_lines) + "\n```"
        
        merged_metadata = sub_chunks[0]["metadata"].copy()
        merged_metadata["is_merged"] = True
        merged_metadata["merged_from_parts"] = len(sub_chunks)
        
        return {
            "id": sub_chunks[0]["id"],
            "text": merged_text,
            "metadata": merged_metadata,
            "similarity": sub_chunks[0].get("similarity", 0),
        }
    
    def _merge_list_chunks(self, sub_chunks: List[Dict]) -> Dict:
        """合并列表子块"""
        # 简单拼接所有列表项
        all_items = []
        for chunk in sub_chunks:
            all_items.append(chunk["text"])
        
        merged_text = '\n'.join(all_items)
        
        merged_metadata = sub_chunks[0]["metadata"].copy()
        merged_metadata["is_merged"] = True
        merged_metadata["merged_from_parts"] = len(sub_chunks)
        
        return {
            "id": sub_chunks[0]["id"],
            "text": merged_text,
            "metadata": merged_metadata,
            "similarity": sub_chunks[0].get("similarity", 0),
        }
    
    def _merge_generic_chunks(self, sub_chunks: List[Dict]) -> Dict:
        """合并通用子块"""
        # 简单拼接
        merged_text = '\n\n'.join([chunk["text"] for chunk in sub_chunks])
        
        merged_metadata = sub_chunks[0]["metadata"].copy()
        merged_metadata["is_merged"] = True
        merged_metadata["merged_from_parts"] = len(sub_chunks)
        
        return {
            "id": sub_chunks[0]["id"],
            "text": merged_text,
            "metadata": merged_metadata,
            "similarity": sub_chunks[0].get("similarity", 0),
        }
```

#### 4. 集成到 RAG 流程

```python
# rag/retrieval/rag_service.py

from rag.retrieval.merge_service import RetrievalMergeService

class RAGService:
    def __init__(self):
        self.merge_service = RetrievalMergeService()
    
    async def query(
        self,
        query: str,
        kb_id: UUID,
        tenant_id: UUID,
        top_k: int = 5
    ) -> Dict:
        """RAG 查询"""
        # 1. 生成查询向量
        query_embedding = await self.embed_query(query)
        
        # 2. 检索并合并（关键步骤）
        retrieved_chunks = await self.merge_service.retrieve_and_merge(
            query_embedding=query_embedding,
            kb_id=kb_id,
            tenant_id=tenant_id,
            top_k=top_k
        )
        
        # 3. 构建 prompt
        context = self._build_context(retrieved_chunks)
        
        # 4. 调用 LLM
        response = await self.generate_response(query, context)
        
        return {
            "answer": response,
            "sources": retrieved_chunks,
        }
```

## 优化建议

### 1. 缓存策略

对于频繁检索的元素，可以缓存合并后的结果：

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def _get_merged_element(element_id: str) -> Dict:
    """缓存合并后的元素"""
    # ... 实现
```

### 2. 异步批量查询

如果有多个拆分元素，使用批量查询提高性能：

```python
async def _get_all_sub_chunks_batch(element_ids: List[str]) -> Dict:
    """批量获取所有子块"""
    # 一次查询获取所有子块
    # ...
```

### 3. 相似度传递

合并时，可以使用最高相似度或平均相似度：

```python
def _merge_sub_chunks(self, sub_chunks: List[Dict]) -> Dict:
    # 使用最高相似度
    max_similarity = max(chunk.get("similarity", 0) for chunk in sub_chunks)
    
    # 或使用平均相似度
    avg_similarity = sum(chunk.get("similarity", 0) for chunk in sub_chunks) / len(sub_chunks)
    
    return {
        # ...
        "similarity": max_similarity,  # 或 avg_similarity
    }
```

## 测试用例

```python
# tests/test_retrieval_merge.py

import pytest
from rag.retrieval.merge_service import RetrievalMergeService

@pytest.mark.asyncio
async def test_merge_table_chunks():
    """测试表格合并"""
    merge_service = RetrievalMergeService()
    
    sub_chunks = [
        {
            "id": "chunk_1",
            "text": "| 列1 | 列2 |\n|-----|-----|\n| 1 | 2 |\n| 3 | 4 |",
            "metadata": {"element_type": "table", "split_part": 1},
            "similarity": 0.9,
        },
        {
            "id": "chunk_2",
            "text": "| 列1 | 列2 |\n|-----|-----|\n| 5 | 6 |\n| 7 | 8 |",
            "metadata": {"element_type": "table", "split_part": 2},
            "similarity": 0.85,
        },
    ]
    
    merged = merge_service._merge_table_chunks(sub_chunks)
    
    assert "| 列1 | 列2 |" in merged["text"]
    assert "| 1 | 2 |" in merged["text"]
    assert "| 5 | 6 |" in merged["text"]
    assert merged["metadata"]["is_merged"] is True
    assert merged["metadata"]["merged_from_parts"] == 2

@pytest.mark.asyncio
async def test_retrieve_and_merge():
    """测试完整的检索合并流程"""
    # ... 实现
```

## 总结

这个方案实现了：
1. ✅ 向量化时使用子块（提高检索精度）
2. ✅ 传递给 LLM 时使用完整元素（保持语义完整性）
3. ✅ 不需要修改数据库结构
4. ✅ 存储高效（不冗余）
5. ✅ 灵活可扩展

下一步：
1. 在 `markdown_chunker.py` 中添加 `original_element_id`
2. 实现 `RetrievalMergeService`
3. 集成到 RAG 流程
4. 编写测试用例
