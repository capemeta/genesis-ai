"""
网页同步接口
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from models.user import User
from schemas.kb_web_sync import (
    WebPageCreateRequest,
    WebPageListRequest,
    WebPagePreviewRequest,
    WebPageUpdateRequest,
    WebPageToggleRequest,
    WebScheduleCreateRequest,
    WebLatestCheckRequest,
    WebScheduleDeleteRequest,
    WebScheduleListRequest,
    WebScheduleUpdateRequest,
    WebSyncNowRequest,
    WebSyncNowByKBDocRequest,
    WebSyncRunListRequest,
)
from services.web_sync_service import WebSyncService
from api.v1.deps import get_current_user

router = APIRouter(prefix="/knowledge-bases/web-sync", tags=["knowledge-bases-web"])


@router.post("/pages/create", summary="创建网页资源")
async def create_web_page(
    request: WebPageCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """创建网页资源。"""
    service = WebSyncService(session)
    data = await service.create_page(
        kb_id=request.kb_id,
        url=request.url,
        folder_id=request.folder_id,
        display_name=request.display_name,
        fetch_mode=request.fetch_mode,
        page_config=request.page_config,
        trigger_sync_now=request.trigger_sync_now,
        current_user=current_user,
    )
    return {"success": True, "data": data}


@router.post("/pages/list", summary="分页查询网页资源")
async def list_web_pages(
    request: WebPageListRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """分页查询网页资源。"""
    service = WebSyncService(session)
    items, total = await service.list_pages(
        kb_id=request.kb_id,
        current_user=current_user,
        page=request.page,
        page_size=request.page_size,
        search=request.search,
        sync_status=request.sync_status,
        folder_id=request.folder_id,
        include_subfolders=request.include_subfolders,
    )
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": request.page,
            "page_size": request.page_size,
        },
    }


@router.post("/pages/update", summary="更新网页资源")
async def update_web_page(
    request: WebPageUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """更新网页资源（标题/URL/归属目录）。"""
    service = WebSyncService(session)
    data = await service.update_page(
        kb_web_page_id=request.kb_web_page_id,
        url=request.url,
        display_name=request.display_name,
        folder_id=request.folder_id,
        fetch_mode=request.fetch_mode,
        page_config=request.page_config,
        current_user=current_user,
    )
    return {"success": True, "data": data}


@router.post("/pages/toggle-enabled", summary="启停网页资源")
async def toggle_web_page_enabled(
    request: WebPageToggleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """启停网页资源。"""
    service = WebSyncService(session)
    data = await service.toggle_page_enabled(
        kb_web_page_id=request.kb_web_page_id,
        is_enabled=request.is_enabled,
        current_user=current_user,
    )
    return {"success": True, "data": data}


@router.post("/pages/preview", summary="网页抽取预览")
async def preview_web_page(
    request: WebPagePreviewRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """执行网页抽取预览，不写入版本和分块。"""
    service = WebSyncService(session)
    data = await service.preview_page(
        kb_web_page_id=request.kb_web_page_id,
        content_selector=request.content_selector,
        fetch_mode=request.fetch_mode,
        timeout_seconds=request.timeout_seconds,
        include_raw_html=request.include_raw_html,
        current_user=current_user,
    )
    return {"success": True, "data": data}


@router.post("/schedules/create", summary="创建同步规则")
async def create_web_schedule(
    request: WebScheduleCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """创建同步规则。"""
    service = WebSyncService(session)
    data = await service.create_schedule(payload=request.model_dump(), current_user=current_user)
    return {"success": True, "data": data}


@router.post("/schedules/update", summary="更新同步规则")
async def update_web_schedule(
    request: WebScheduleUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """更新同步规则。"""
    service = WebSyncService(session)
    payload = request.model_dump(exclude_none=True)
    schedule_id = payload.pop("schedule_id")
    data = await service.update_schedule(
        schedule_id=schedule_id,
        payload=payload,
        current_user=current_user,
    )
    return {"success": True, "data": data}


@router.post("/schedules/list", summary="查询同步规则")
async def list_web_schedules(
    request: WebScheduleListRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """查询同步规则。"""
    service = WebSyncService(session)
    data = await service.list_schedules(
        kb_id=request.kb_id,
        kb_web_page_id=request.kb_web_page_id,
        current_user=current_user,
    )
    return {"success": True, "data": data}


@router.post("/schedules/delete", summary="删除同步规则")
async def delete_web_schedule(
    request: WebScheduleDeleteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """删除同步规则。"""
    service = WebSyncService(session)
    data = await service.delete_schedule(
        schedule_id=request.schedule_id,
        current_user=current_user,
    )
    return {"success": True, "data": data}


@router.post("/runs/sync-now", summary="立即同步网页")
async def sync_web_page_now(
    request: WebSyncNowRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """立即触发网页同步。"""
    service = WebSyncService(session)
    data = await service.trigger_sync_now(
        kb_web_page_id=request.kb_web_page_id,
        force_rebuild_index=request.force_rebuild_index,
        current_user=current_user,
    )
    return {"success": True, "message": "同步任务已入队", "data": data}


@router.post("/runs/sync-now-by-kb-doc", summary="按知识库文档ID立即同步网页")
async def sync_web_page_now_by_kb_doc(
    request: WebSyncNowByKBDocRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """按知识库文档ID立即触发网页同步。"""
    service = WebSyncService(session)
    data = await service.trigger_sync_now_by_kb_doc(
        kb_doc_id=request.kb_doc_id,
        force_rebuild_index=request.force_rebuild_index,
        current_user=current_user,
    )
    return {"success": True, "message": "同步任务已入队", "data": data}


@router.post("/runs/latest-check", summary="校验网页是否为最新版本")
async def latest_check_web_page(
    request: WebLatestCheckRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """执行最新性校验。"""
    service = WebSyncService(session)
    data = await service.latest_check(
        kb_web_page_id=request.kb_web_page_id,
        current_user=current_user,
    )
    return {"success": True, "data": data}


@router.post("/runs/list", summary="分页查询同步记录")
async def list_web_sync_runs(
    request: WebSyncRunListRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """分页查询同步记录。"""
    service = WebSyncService(session)
    items, total = await service.list_runs(
        kb_id=request.kb_id,
        current_user=current_user,
        page=request.page,
        page_size=request.page_size,
        kb_web_page_id=request.kb_web_page_id,
        run_status=request.status,
    )
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": request.page,
            "page_size": request.page_size,
        },
    }
