"""
知识库标签 API（resource_tags.target_type=kb）
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from core.security.auth import get_current_user
from models.knowledge_base import KnowledgeBase
from models.tag import Tag
from models.user import User
from schemas.tag import KbTagsRequest, KbTagsResponse
from services.kb_tag_service import KbTagService

router = APIRouter(prefix="/kb-tags", tags=["kb-tags"])


async def _get_kb_or_404(
    *,
    session: AsyncSession,
    kb_id: UUID,
    current_user: User,
) -> KnowledgeBase:
    kb = await session.get(KnowledgeBase, kb_id)
    if not kb or kb.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    return kb


@router.post("/get", response_model=KbTagsResponse)
async def get_kb_tags(
    request: dict,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """获取知识库标签。"""
    kb_id = UUID(request["kb_id"])
    await _get_kb_or_404(session=session, kb_id=kb_id, current_user=current_user)
    tags = await KbTagService.get_kb_tags(session=session, kb_id=kb_id, tenant_id=current_user.tenant_id)
    return {"kb_id": kb_id, "tags": tags}


@router.post("/set", response_model=KbTagsResponse)
async def set_kb_tags(
    request: KbTagsRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """设置知识库标签（全量替换）。"""
    await _get_kb_or_404(session=session, kb_id=request.kb_id, current_user=current_user)

    invalid_tag_ids: list[str] = []
    for tag_id in request.tag_ids:
        tag = await session.get(Tag, tag_id)
        if not tag or tag.tenant_id != current_user.tenant_id:
            invalid_tag_ids.append(str(tag_id))
            continue
        if tag.kb_id is not None and tag.kb_id != request.kb_id:
            invalid_tag_ids.append(str(tag_id))
            continue
        if "kb" not in (tag.allowed_target_types or ["kb_doc"]):
            invalid_tag_ids.append(str(tag_id))
    if invalid_tag_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"存在不属于当前知识库作用域或不适用于知识库的标签: {', '.join(invalid_tag_ids)}",
        )

    tags = await KbTagService.set_kb_tags(
        session=session,
        kb_id=request.kb_id,
        tag_ids=request.tag_ids,
        tenant_id=current_user.tenant_id,
    )
    return {"kb_id": request.kb_id, "tags": tags}
