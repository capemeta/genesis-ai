"""
知识库文档标签 API（resource_tags.target_type=kb_doc）
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from core.security.auth import get_current_user
from models.user import User
from models.knowledge_base_document import KnowledgeBaseDocument
from schemas.tag import KbDocTagsRequest, KbDocTagsResponse
from services.kb_doc_tag_service import KbDocTagService

router = APIRouter(prefix="/kb-doc-tags", tags=["kb-doc-tags"])


@router.post("/get", response_model=KbDocTagsResponse)
async def get_kb_doc_tags(
    request: dict,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """
    获取知识库文档的标签

    请求体：
    - kb_doc_id: 知识库文档ID（knowledge_base_documents.id）
    """
    from uuid import UUID

    kb_doc_id = UUID(request["kb_doc_id"])
    kb_doc = await session.get(KnowledgeBaseDocument, kb_doc_id)
    if not kb_doc or kb_doc.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在",
        )

    tags = await KbDocTagService.get_kb_doc_tags(
        session=session,
        kb_doc_id=kb_doc_id,
        tenant_id=current_user.tenant_id,
    )
    return {"kb_doc_id": kb_doc_id, "tags": tags}



