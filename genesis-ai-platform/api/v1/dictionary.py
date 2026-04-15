"""
术语与同义词扩展 API

说明：
- 标准 CRUD 由 CRUD 工厂自动生成。
- 本文件仅保留轻量扩展路由，核心逻辑在 service 层。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from core.response import ResponseBuilder
from core.security.auth import get_current_user
from models.kb_synonym import KBSynonym
from models.user import User
from schemas.dictionary import SynonymRewritePreviewRequest, SynonymRewritePreviewResponse
from schemas.dictionary import (
    SynonymVariantBatchUpsertRequest,
    SynonymVariantBatchUpsertResponse,
)
from services.dictionary_service import KBSynonymService, KBSynonymVariantService
from models.kb_synonym_variant import KBSynonymVariant

router = APIRouter(prefix="/dictionary", tags=["dictionary"])


@router.post("/synonyms/rewrite-preview", response_model=dict)
async def rewrite_preview(
    request: SynonymRewritePreviewRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """同义词改写预览（仅预览，不落库）。"""
    service = KBSynonymService(model=KBSynonym, db=session)
    result: SynonymRewritePreviewResponse = await service.rewrite_query_preview(
        tenant_id=current_user.tenant_id,
        query=request.query,
        kb_id=request.kb_id,
    )
    return ResponseBuilder.build_success(
        data=result.model_dump(),
        message="改写预览成功",
    )


@router.post("/synonyms/variants/batch-upsert", response_model=dict)
async def batch_upsert_synonym_variants(
    request: SynonymVariantBatchUpsertRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """同义词口语批量维护。"""
    service = KBSynonymVariantService(model=KBSynonymVariant, db=session)
    result: SynonymVariantBatchUpsertResponse = await service.batch_upsert_variants(
        synonym_id=request.synonym_id,
        variants=request.variants,
        replace=request.replace,
        current_user=current_user,
    )
    return ResponseBuilder.build_success(
        data=result.model_dump(),
        message="批量维护口语词成功",
    )
