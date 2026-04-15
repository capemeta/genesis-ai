"""
QA 分块器测试
"""

from rag.ingestion.chunkers.qa.qa_chunker import QAChunker


def test_qa_chunker_short_answer_stays_single_leaf_chunk() -> None:
    """短答案应直接生成单个可检索叶子块。"""
    chunker = QAChunker(chunk_size=120, chunk_overlap=20)
    chunks = chunker.chunk(
        "",
        {
            "qa_items": [
                {
                    "qa_row_id": "row-1",
                    "question": "如何重置密码？",
                    "answer": "进入个人中心的安全设置页面，点击重置密码即可。",
                    "similar_questions": ["忘记密码怎么办"],
                    "tags": ["账号"],
                    "category": "账号管理",
                    "source_row": 2,
                    "source_sheet_name": "Sheet1",
                    "source_mode": "imported",
                    "position": 0,
                }
            ]
        },
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    meta = chunk["metadata"]

    assert meta["chunk_role"] == "qa_row"
    assert meta["is_leaf"] is True
    assert meta["should_vectorize"] is True
    assert meta["child_ids"] == []
    assert meta["source_anchors"] == ["Sheet1!R2"]
    assert meta["source_element_indices"] == [2]
    assert "## 问题\n如何重置密码？" in chunk["text"]
    assert "## 答案\n进入个人中心的安全设置页面，点击重置密码即可。" in chunk["text"]
    assert len(chunk["content_blocks"]) >= 2


def test_qa_chunker_long_answer_emits_parent_and_children() -> None:
    """长答案应输出父块与多个答案子块，并保持统一层级字段。"""
    answer = (
        "第一步，准备相关资料并登录系统。"
        "第二步，进入对应页面逐项核对信息。"
        "第三步，提交申请后等待审核反馈。"
        "第四步，如审核失败，根据提示修改后重新提交。"
    )
    chunker = QAChunker(chunk_size=30, chunk_overlap=5)
    chunks = chunker.chunk(
        "",
        {
            "qa_items": [
                {
                    "qa_row_id": "row-2",
                    "question": "如何办理申请？",
                    "answer": answer,
                    "similar_questions": [],
                    "tags": ["流程"],
                    "category": "办事指南",
                    "source_mode": "manual",
                    "position": 3,
                }
            ]
        },
    )

    assert len(chunks) >= 3
    parent_chunk = chunks[0]
    parent_meta = parent_chunk["metadata"]

    assert parent_meta["chunk_role"] == "qa_row"
    assert parent_meta["is_leaf"] is False
    assert parent_meta["should_vectorize"] is False
    assert parent_meta["exclude_from_retrieval"] is True
    assert len(parent_meta["child_ids"]) == len(chunks) - 1

    child_chunks = chunks[1:]
    for index, chunk in enumerate(child_chunks, start=1):
        meta = chunk["metadata"]
        assert meta["chunk_role"] == "qa_answer_fragment"
        assert meta["parent_id"] == parent_meta["node_id"]
        assert meta["is_leaf"] is True
        assert meta["should_vectorize"] is True
        assert meta["answer_part_index"] == index
        assert meta["answer_part_total"] == len(child_chunks)
        assert chunk["text"].startswith("## 问题\n如何办理申请？")
        assert "\n## 答案\n" in chunk["text"]
