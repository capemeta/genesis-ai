from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from uuid import UUID as PyUUID

from fastapi import HTTPException
from sqlalchemy import select, func

from core.base_service import BaseService
from models.chunk import Chunk
from models.user import User
from rag.utils.token_utils import count_tokens
from schemas.chunk import ChunkCreate, ChunkUpdate

_EDIT_HARD_LIMIT_TOKENS = 2000

_EXCEL_CANONICAL_CHUNK_ROLES = {
    "excel_sheet_root",
    "excel_row",
    "excel_row_fragment",
    "excel_general_group",
    "excel_general_fallback",
}


def _normalize_chunk_metadata_info(metadata_info: Dict[str, Any]) -> Dict[str, Any]:
    """规范化切片增强协议，统一使用 metadata_info.enhancement。"""
    normalized = dict(metadata_info)
    enhancement_raw = normalized.get("enhancement")
    enhancement = dict(enhancement_raw) if isinstance(enhancement_raw, dict) else {}

    # 开发阶段不兼容旧协议，保存时直接清理旧键，避免再次写回。
    normalized.pop("tags", None)
    normalized.pop("retrieval_questions", None)

    if enhancement:
        normalized["enhancement"] = enhancement
    elif "enhancement" in normalized:
        normalized["enhancement"] = {}

    return normalized


def _compose_search_content_from_blocks(content_blocks: List[Dict[str, Any]], fallback_text: str) -> str:
    parts: List[str] = []
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").lower()
        if block_type == "title":
            markdown = str(block.get("markdown") or "").strip()
            text = markdown or str(block.get("text") or "").strip()
            if text:
                parts.append(text)
            continue
        if block_type in {"text", "code", "table", "html", "json"}:
            text = str(block.get("text") or "").strip()
            if text:
                parts.append(text)
            continue
        if block_type == "image":
            url = str(block.get("url") or "").strip()
            alt_text = str(block.get("alt_text") or "").strip()
            analysis_raw = block.get("analysis")
            analysis: Dict[str, Any] = analysis_raw if isinstance(analysis_raw, dict) else {}
            status = str(analysis.get("status") or "none").strip().lower()
            ocr_text = str(analysis.get("ocr_text") or "").strip()
            vision_summary = str(analysis.get("vision_text") or "").strip()
            if url:
                parts.append(f"![{alt_text or 'image'}]({url})")
            if status in {"ocr", "ocr_vision"} and ocr_text:
                parts.append(f"[IMAGE OCR]\n{ocr_text}")
            if status in {"vision", "ocr_vision"} and vision_summary:
                parts.append(f"[IMAGE VISION]\n{vision_summary}")
    merged = "\n\n".join(p for p in parts if p).strip()
    return merged or (fallback_text or "").strip()


def _build_original_content_baseline(chunk: Chunk) -> str:
    """基于原始结构化内容生成稳定的默认文本基线。"""
    chunk_role = str((chunk.metadata_info or {}).get("chunk_role") or "").strip()

    # Excel 的 content 已经是当前约定的检索/展示主文本。
    # 恢复默认内容时应回到这条 canonical 文本，而不是从 content_blocks 的表格 Markdown 反推，
    # 否则会把用户看到的键值对文本恢复成 Markdown 表格，前后语义不一致。
    if chunk_role in _EXCEL_CANONICAL_CHUNK_ROLES:
        return (chunk.content or "").strip()

    content_blocks = chunk.content_blocks if isinstance(chunk.content_blocks, list) else []
    return _compose_search_content_from_blocks(content_blocks, chunk.content or "")


class ChunkService(BaseService[Chunk, ChunkCreate, ChunkUpdate]):
    async def get_by_node_id(
        self,
        node_id: str,
        tenant_id: Optional[PyUUID] = None,
        user_id: Optional[PyUUID] = None,
        check_permission: bool = True,
    ) -> Chunk:
        """根据 metadata_info.node_id 获取切片。"""
        normalized_node_id = str(node_id or "").strip()
        if not normalized_node_id:
            raise HTTPException(status_code=400, detail="node_id 不能为空")

        conditions = [self.model.metadata_info["node_id"].astext == normalized_node_id]

        if hasattr(self.model, "tenant_id") and tenant_id is not None:
            conditions.append(self.model.tenant_id == tenant_id)

        stmt = select(self.model).where(*conditions)
        resource = (await self.db.execute(stmt)).scalar_one_or_none()

        if not resource:
            raise HTTPException(status_code=404, detail=f"未找到 node_id={normalized_node_id} 对应的切片")

        return resource

    async def list_resources(
        self,
        tenant_id: Optional[PyUUID] = None,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        advanced_filters: Optional[List[Dict[str, Any]]] = None,
        order_by: str = "created_at desc",
        user_id: Optional[PyUUID] = None,
        include_public: bool = True,
    ) -> Tuple[List[Chunk], int]:
        # Copy incoming filters to avoid mutating caller-owned objects.
        base_filters = dict(filters or {})
        meta_filters: Dict[str, Any] = {}
        for key in ("node_id", "is_root", "is_leaf"):
            if key in base_filters:
                meta_filters[key] = base_filters.pop(key)

        resources, total = await super().list_resources(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            search=search,
            filters=base_filters or None,
            advanced_filters=advanced_filters,
            order_by=order_by,
            user_id=user_id,
            include_public=include_public,
        )

        if not meta_filters:
            return resources, total

        conditions = []
        if tenant_id:
            conditions.append(self.model.tenant_id == tenant_id)
        for k, v in base_filters.items():
            if hasattr(self.model, k):
                conditions.append(getattr(self.model, k) == v)

        for k, v in meta_filters.items():
            if k in ("is_root", "is_leaf"):
                conditions.append(self.model.metadata_info[k].astext == ("true" if v else "false"))
            else:
                conditions.append(self.model.metadata_info[k].astext == str(v))

        count_stmt = select(func.count()).select_from(self.model).where(*conditions)
        total = await self.db.scalar(count_stmt) or 0

        offset = (page - 1) * page_size
        stmt = select(self.model).where(*conditions).offset(offset).limit(page_size)
        if order_by:
            if "created_at" in order_by:
                stmt = stmt.order_by(self.model.created_at.desc() if "desc" in order_by else self.model.created_at.asc())
            elif "position" in order_by:
                stmt = stmt.order_by(self.model.position.asc() if "asc" in order_by else self.model.position.desc())

        result = await self.db.execute(stmt)
        resources = result.scalars().all()
        return list(resources), total

    async def update(
        self,
        resource_id: int,
        data: ChunkUpdate,
        current_user: Optional[User] = None,
    ) -> Chunk:
        chunk = await self.get_by_id(
            resource_id,
            current_user.tenant_id if current_user and hasattr(current_user, "tenant_id") else None,
            current_user.id if current_user and hasattr(current_user, "id") else None,
            check_permission=True if current_user else False,
        )

        if isinstance(data, dict):
            update_data = data
        elif hasattr(data, "model_dump"):
            update_data = data.model_dump(exclude_unset=True)
        else:
            update_data = data.dict(exclude_unset=True)

        if "content" in update_data and update_data["content"] is not None:
            edited_text = str(update_data["content"])
            original_baseline = _build_original_content_baseline(chunk)
            token_total = count_tokens(edited_text)
            if token_total > _EDIT_HARD_LIMIT_TOKENS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"编辑后分块过大：{token_total} tokens，超过上限 {_EDIT_HARD_LIMIT_TOKENS}，"
                        "请拆分后再保存"
                    ),
                )

            is_edited = edited_text != original_baseline
            update_data["content"] = edited_text
            update_data["token_count"] = token_total
            update_data["text_length"] = len(edited_text)
            update_data["is_content_edited"] = is_edited
            update_data["original_content"] = original_baseline if is_edited else None

            edit_meta: Dict[str, Any] = {
                "content_edited": is_edited,
            }
            if is_edited:
                edit_meta["content_edited_at"] = datetime.utcnow().isoformat() + "Z"
            else:
                edit_meta["content_edited_at"] = None
            if isinstance(update_data.get("metadata_info"), dict):
                update_data["metadata_info"] = {**update_data["metadata_info"], **edit_meta}
            else:
                update_data["metadata_info"] = edit_meta

        if "metadata_info" in update_data and update_data["metadata_info"] is not None:
            current_metadata = chunk.metadata_info or {}
            new_metadata = update_data["metadata_info"]
            update_data["metadata_info"] = _normalize_chunk_metadata_info({**current_metadata, **new_metadata})

        updated_data = ChunkUpdate(**update_data)
        return await super().update(resource_id, updated_data, current_user)
