"""
网页同步任务

包含：
- 动态调度分发任务（扫描 kb_web_sync_schedules 并入队）
- 网页同步执行任务（抓取 + 抽取 + 变更检测 + 分块写入）
"""
import asyncio
import hashlib
import logging
from io import BytesIO
from pathlib import Path
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from uuid import UUID

import httpx
import redis.exceptions as redis_exc
from croniter import croniter  # type: ignore[import-untyped]
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from core.database.session import (
    close_task_db_engine,
    close_task_redis_client,
    create_task_redis_client,
    create_task_session_maker,
)
from models.document import Document
from models.kb_web_page import KBWebPage
from models.kb_web_page_version import KBWebPageVersion
from models.kb_web_sync_run import KBWebSyncRun
from models.kb_web_sync_schedule import KBWebSyncSchedule
from models.knowledge_base_document import KnowledgeBaseDocument
from models.knowledge_base import KnowledgeBase
from rag.ingestion.tasks.common import (
    add_log,
    build_effective_config,
    finalize_latest_attempt,
    set_runtime_stage,
    sync_latest_attempt_snapshot,
)
from services.kb_document_parse_service import (
    dispatch_parse_pipeline,
    prepare_parse_pipeline_submission,
)
from services.web_content_extractor import extract_web_content
from tasks.celery_tasks import celery_app

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _extract_force_rebuild_index(run: KBWebSyncRun) -> bool:
    """从运行日志中提取“始终重建索引”开关。"""
    for entry in reversed(list(run.logs_json or [])):
        if not isinstance(entry, dict):
            continue
        detail = dict(entry.get("detail") or {})
        if "force_rebuild_index" in detail:
            return bool(detail.get("force_rebuild_index"))
    return False


def _append_run_log(
    run: KBWebSyncRun,
    *,
    level: str,
    stage: str,
    message: str,
    detail: Optional[dict] = None,
) -> None:
    """向网页同步运行记录追加结构化日志。"""
    run.logs_json = list(run.logs_json or []) + [{
        "time": _now_utc().isoformat(),
        "level": level,
        "stage": stage,
        "message": message,
        "detail": detail or {},
    }]


async def _acquire_lock(redis_client, key: str, ttl_seconds: int) -> Optional[str]:
    token = hashlib.sha256(f"{key}:{_now_utc().isoformat()}".encode("utf-8")).hexdigest()
    ok = await redis_client.set(key, token, nx=True, ex=ttl_seconds)
    return token if ok else None


async def _release_lock(redis_client, key: str, token: str) -> None:
    lua = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
else
  return 0
end
"""
    try:
        await redis_client.eval(lua, 1, key, token)
    except Exception:  # noqa: BLE001
        logger.warning("释放锁失败 key=%s", key, exc_info=True)


def _compute_next_trigger_at(
    *,
    schedule_type: str,
    cron_expr: Optional[str],
    timezone_name: str,
    interval_value: Optional[int],
    interval_unit: Optional[str],
    run_time: Optional[time],
    run_date: Optional[date],
    weekdays: list[int],
    monthdays: list[int],
    start_at: Optional[datetime],
    now_utc: datetime,
) -> Optional[datetime]:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone_name or "Asia/Shanghai")
    now_local = now_utc.astimezone(tz)
    if start_at:
        now_local = max(now_local, start_at.astimezone(tz))

    if schedule_type == "manual":
        return None
    if schedule_type == "interval":
        if not interval_value:
            return None
        unit = interval_unit or "minute"
        if unit == "minute":
            next_local = now_local + timedelta(minutes=interval_value)
        elif unit == "hour":
            next_local = now_local + timedelta(hours=interval_value)
        else:
            next_local = now_local + timedelta(days=interval_value)
        return next_local.astimezone(timezone.utc)

    if schedule_type == "once":
        if not run_date:
            return None
        scheduled_time = run_time or time(hour=0, minute=0)
        local_dt = datetime.combine(run_date, scheduled_time, tzinfo=tz)
        if local_dt <= now_local:
            return None
        return local_dt.astimezone(timezone.utc)

    if schedule_type == "daily":
        if not run_time:
            return None
        cron_text = f"{run_time.minute} {run_time.hour} * * *"
    elif schedule_type == "weekly":
        if not run_time or not weekdays:
            return None
        weekday_text = ",".join(str(int(day)) for day in weekdays)
        cron_text = f"{run_time.minute} {run_time.hour} * * {weekday_text}"
    elif schedule_type == "monthly":
        if not run_time or not monthdays:
            return None
        monthday_text = ",".join(str(int(day)) for day in monthdays)
        cron_text = f"{run_time.minute} {run_time.hour} {monthday_text} * *"
    elif schedule_type == "cron":
        if not cron_expr:
            return None
        cron_text = cron_expr
    else:
        return None

    iterator = croniter(cron_text, now_local)
    return iterator.get_next(datetime).astimezone(timezone.utc)


def _build_web_sync_error_message(
    *,
    page: KBWebPage,
    exc: Exception,
    stage: str,
    timeout_seconds: int | None = None,
) -> tuple[str, dict]:
    """构造用户可读错误摘要与结构化诊断信息。"""
    exc_type = exc.__class__.__name__
    raw_message = str(exc).strip()
    fetch_mode = str(page.fetch_mode or "auto").strip()
    target_url = str(page.url or "").strip()

    if isinstance(exc, httpx.ConnectTimeout):
        summary = (
            f"网页同步失败：访问 {target_url} 时连接超时"
            f"（阶段={stage}，抓取模式={fetch_mode}，超时={timeout_seconds or 0}s，异常={exc_type}）"
        )
    elif isinstance(exc, httpx.ReadTimeout):
        summary = (
            f"网页同步失败：访问 {target_url} 时响应超时"
            f"（阶段={stage}，抓取模式={fetch_mode}，超时={timeout_seconds or 0}s，异常={exc_type}）"
        )
    elif isinstance(exc, httpx.ConnectError):
        summary = (
            f"网页同步失败：访问 {target_url} 时建立连接失败"
            f"（阶段={stage}，抓取模式={fetch_mode}，异常={exc_type}）"
        )
    else:
        detail = raw_message or repr(exc)
        summary = (
            f"网页同步失败：访问 {target_url} 时发生异常"
            f"（阶段={stage}，抓取模式={fetch_mode}，异常={exc_type}，详情={detail}）"
        )

    detail_payload = {
        "stage": stage,
        "url": target_url,
        "fetch_mode": fetch_mode,
        "timeout_seconds": timeout_seconds,
        "exception_type": exc_type,
        "raw_message": raw_message or repr(exc),
    }
    return summary[:2000], detail_payload


async def _persist_raw_html_snapshot_document(
    *,
    session,
    page: KBWebPage,
    run: KBWebSyncRun,
    source_document: Document,
    raw_html: str,
    existing_snapshot_doc: Optional[Document] = None,
) -> Optional[UUID]:
    """保存原始 HTML 快照到 documents + storage（仅保留最新版本，覆盖写）。"""
    html_text = str(raw_html or "").strip()
    if not html_text:
        return None

    html_bytes = html_text.encode("utf-8")
    html_hash = hashlib.sha256(html_bytes).hexdigest()
    html_name = f"{Path(source_document.name).stem}_raw_latest.html"

    snapshot_doc = existing_snapshot_doc
    if snapshot_doc is None:
        snapshot_doc = Document(
            tenant_id=page.tenant_id,
            owner_id=source_document.owner_id,
            name=html_name,
            file_type="HTML",
            storage_driver=source_document.storage_driver,
            bucket_name=source_document.bucket_name,
            file_key="",
            file_size=len(html_bytes),
            mime_type="text/html",
            carrier_type="generated_snapshot",
            asset_kind="virtual",
            source_type="system",
            source_url=page.url,
            content_hash=html_hash,
            metadata_info={
                "snapshot_kind": "web_raw_html",
                "retention_mode": "latest_only",
                "parent_document_id": str(source_document.id),
                "kb_doc_id": str(page.kb_doc_id),
                "kb_web_page_id": str(page.id),
                "run_id": str(run.id),
            },
            created_by_id=run.triggered_by_id,
            created_by_name=run.triggered_by_name,
            updated_by_id=run.triggered_by_id,
            updated_by_name=run.triggered_by_name,
        )
        session.add(snapshot_doc)
        await session.flush()
    else:
        snapshot_doc.name = html_name
        snapshot_doc.file_size = len(html_bytes)
        snapshot_doc.mime_type = "text/html"
        snapshot_doc.source_url = page.url
        snapshot_doc.content_hash = html_hash
        snapshot_doc.updated_by_id = run.triggered_by_id
        snapshot_doc.updated_by_name = run.triggered_by_name
        snapshot_doc.updated_at = _now_utc()
        metadata = dict(snapshot_doc.metadata_info or {})
        metadata.update(
            {
                "snapshot_kind": "web_raw_html",
                "retention_mode": "latest_only",
                "parent_document_id": str(source_document.id),
                "kb_doc_id": str(page.kb_doc_id),
                "kb_web_page_id": str(page.id),
                "run_id": str(run.id),
            }
        )
        snapshot_doc.metadata_info = metadata

    file_key = f"{page.tenant_id}/parsed/web_raw_html/{page.id}/latest.html"
    snapshot_doc.file_key = file_key

    # 延迟导入存储驱动，避免 Celery 启动时因为 S3 依赖初始化过早而放大内存占用。
    from core.storage import get_storage_driver

    storage_driver = get_storage_driver(source_document.storage_driver)
    await storage_driver.upload(
        file=BytesIO(html_bytes),
        key=file_key,
        content_type="text/html",
    )
    return snapshot_doc.id


async def _dispatch_due_web_sync_jobs(batch_size: int = 100) -> dict:
    task_engine, task_sm = create_task_session_maker()
    redis_client = create_task_redis_client()
    dispatched_runs = 0
    touched_schedules = 0
    now = _now_utc()

    pending_run_ids: list[str] = []
    try:
        async with task_sm() as session:
            due_stmt = (
                select(KBWebSyncSchedule)
                .where(
                    KBWebSyncSchedule.is_enabled.is_(True),
                    KBWebSyncSchedule.next_trigger_at.is_not(None),
                    KBWebSyncSchedule.next_trigger_at <= now,
                    (KBWebSyncSchedule.start_at.is_(None) | (KBWebSyncSchedule.start_at <= now)),
                    (KBWebSyncSchedule.end_at.is_(None) | (KBWebSyncSchedule.end_at > now)),
                )
                .order_by(KBWebSyncSchedule.priority.asc(), KBWebSyncSchedule.next_trigger_at.asc())
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            schedules = (await session.execute(due_stmt)).scalars().all()

            for schedule in schedules:
                lock_key = f"lock:web_sync:schedule:{schedule.id}"
                token = await _acquire_lock(redis_client, lock_key, ttl_seconds=240)
                if not token:
                    continue
                try:
                    page_stmt = select(KBWebPage).where(
                        KBWebPage.tenant_id == schedule.tenant_id,
                        KBWebPage.kb_id == schedule.kb_id,
                        KBWebPage.is_enabled.is_(True),
                    )
                    if schedule.kb_web_page_id:
                        page_stmt = page_stmt.where(KBWebPage.id == schedule.kb_web_page_id)
                    pages = (await session.execute(page_stmt.limit(300))).scalars().all()

                    for page in pages:
                        running_stmt = select(KBWebSyncRun.id).where(
                            KBWebSyncRun.kb_web_page_id == page.id,
                            KBWebSyncRun.status.in_(["queued", "running"]),
                        )
                        exists_running = (await session.execute(running_stmt)).scalar_one_or_none()
                        if exists_running:
                            continue

                        kb_doc_stmt = select(KnowledgeBaseDocument).where(
                            KnowledgeBaseDocument.id == page.kb_doc_id
                        )
                        kb_doc = (await session.execute(kb_doc_stmt)).scalar_one_or_none()
                        if not kb_doc:
                            continue

                        trigger_window = now.replace(second=0, microsecond=0).isoformat()
                        dedupe_key = hashlib.sha256(
                            f"{page.id}:{schedule.id}:{trigger_window}".encode("utf-8")
                        ).hexdigest()

                        try:
                            # 使用 savepoint，只回滚冲突记录，避免影响同批次其他调度项。
                            async with session.begin_nested():
                                run = KBWebSyncRun(
                                    tenant_id=page.tenant_id,
                                    kb_id=page.kb_id,
                                    kb_web_page_id=page.id,
                                    kb_doc_id=page.kb_doc_id,
                                    version_id=None,
                                    schedule_id=schedule.id,
                                    trigger_type="scheduled",
                                    status="queued",
                                    dedupe_key=dedupe_key,
                                    started_at=None,
                                    ended_at=None,
                                    duration_ms=None,
                                    http_status=None,
                                    content_changed=None,
                                    old_content_hash=page.latest_content_hash,
                                    new_content_hash=None,
                                    chunks_before=int(kb_doc.chunk_count or 0),
                                    chunks_after=None,
                                    error_message=None,
                                    logs_json=[{
                                        "time": now.isoformat(),
                                        "level": "info",
                                        "stage": "queue",
                                        "message": "定时同步任务已入队",
                                        "detail": {
                                            "force_rebuild_index": False,
                                            "rebuild_policy": "content_changed_only",
                                        },
                                    }],
                                    triggered_by_id=None,
                                    triggered_by_name="scheduler",
                                )
                                session.add(run)
                                page.sync_status = "queued"
                                kb_doc.parse_status = "queued"
                                kb_doc.runtime_stage = "queued"
                                kb_doc.runtime_updated_at = now
                                await session.flush()
                                pending_run_ids.append(str(run.id))
                                dispatched_runs += 1
                        except IntegrityError:
                            # 并发下可能命中 dedupe/running 唯一约束，跳过即可。
                            continue

                    schedule.last_triggered_at = now
                    schedule.next_trigger_at = _compute_next_trigger_at(
                        schedule_type=schedule.schedule_type,
                        cron_expr=schedule.cron_expr,
                        timezone_name=schedule.timezone,
                        interval_value=schedule.interval_value,
                        interval_unit=schedule.interval_unit,
                        run_time=schedule.run_time,
                        run_date=schedule.run_date,
                        weekdays=list(schedule.weekdays or []),
                        monthdays=list(schedule.monthdays or []),
                        start_at=schedule.start_at,
                        now_utc=now,
                    )
                    touched_schedules += 1
                finally:
                    await _release_lock(redis_client, lock_key, token)

            await session.commit()

        # 统一在提交后投递任务，避免任务抢跑读不到 run 记录。
        for run_id in pending_run_ids:
            execute_web_sync_run_task.delay(run_id)

        return {
            "status": "success",
            "touched_schedules": touched_schedules,
            "dispatched_runs": dispatched_runs,
        }
    finally:
        await close_task_redis_client(redis_client)
        await close_task_db_engine(task_engine)


async def _execute_web_sync_run(run_id: UUID) -> dict:
    task_engine, task_sm = create_task_session_maker()
    redis_client = create_task_redis_client()
    started_at = _now_utc()
    try:
        async with task_sm() as session:
            stmt = (
                select(KBWebSyncRun, KBWebPage, KnowledgeBaseDocument, Document, KnowledgeBase)
                .join(KBWebPage, KBWebSyncRun.kb_web_page_id == KBWebPage.id)
                .join(KnowledgeBaseDocument, KBWebSyncRun.kb_doc_id == KnowledgeBaseDocument.id)
                .join(Document, KBWebPage.document_id == Document.id)
                .join(KnowledgeBase, KBWebPage.kb_id == KnowledgeBase.id)
                .where(KBWebSyncRun.id == run_id)
            )
            row = (await session.execute(stmt)).first()
            if not row:
                return {"status": "not_found", "run_id": str(run_id)}

            run, page, kb_doc, document, kb = row
            if run.status not in {"queued", "running"}:
                return {"status": "ignored", "run_id": str(run.id), "reason": f"status={run.status}"}

            page_lock_key = f"lock:web_sync:page:{page.id}"
            page_lock_token = await _acquire_lock(redis_client, page_lock_key, ttl_seconds=1200)
            if not page_lock_token:
                now = _now_utc()
                # 未拿到页面锁时直接结束当前 run，避免长期停留在 queued 状态。
                run.status = "cancelled"
                run.ended_at = now
                run.duration_ms = 0
                run.error_message = "页面正在被其他同步任务处理，当前任务已取消"
                await session.commit()
                return {"status": "cancelled", "run_id": str(run.id), "reason": "page_locked"}

            try:
                force_rebuild_index = _extract_force_rebuild_index(run)
                run.status = "running"
                run.started_at = started_at
                page.sync_status = "syncing"
                kb_doc.parse_status = "processing"
                set_runtime_stage(kb_doc, "syncing")
                _append_run_log(
                    run,
                    level="info",
                    stage="start",
                    message="网页同步开始执行",
                    detail={
                        "force_rebuild_index": force_rebuild_index,
                        "trigger_type": run.trigger_type,
                    },
                )
                await session.commit()

                timeout = int((page.config_json or {}).get("timeout_seconds") or 20)
                content_selector = str((page.config_json or {}).get("content_selector") or "").strip() or None
                extract_result = await extract_web_content(
                    url=page.url,
                    fetch_mode=page.fetch_mode,
                    timeout_seconds=timeout,
                    content_selector=content_selector,
                )
                extracted = extract_result.extracted_text
                final_url = extract_result.final_url
                http_status = extract_result.http_status
                etag = extract_result.etag
                last_modified = extract_result.last_modified
                extractor = extract_result.extractor
                quality_summary = dict(extract_result.quality_summary or {})
                structured_sections = list(extract_result.structured_sections or [])
                raw_html = extract_result.raw_html

                new_hash = hashlib.sha256(extracted.encode("utf-8")).hexdigest()
                old_hash = page.latest_content_hash
                content_changed = bool(old_hash != new_hash)
                now = _now_utc()

                version_id = None
                chunks_before = int(kb_doc.chunk_count or 0)
                chunks_after: int | None = chunks_before
                parse_signature = None

                page.last_synced_at = now
                page.last_http_status = http_status
                page.etag = etag
                page.last_modified = last_modified
                page.last_error = None
                page.sync_status = "success"
                page.content_status = "changed" if content_changed else "unchanged"
                _append_run_log(
                    run,
                    level="info",
                    stage="extract",
                    message="网页正文抽取完成",
                    detail={
                        "extractor": extractor,
                        "http_status": http_status,
                        "final_url": final_url,
                        "text_length": len(extracted),
                        "content_changed": content_changed,
                        "quality_summary": quality_summary,
                    },
                )

                if content_changed:
                    current_version_stmt = (
                        select(KBWebPageVersion)
                        .where(
                            KBWebPageVersion.kb_web_page_id == page.id,
                            KBWebPageVersion.is_current.is_(True),
                        )
                    )
                    current_version = (await session.execute(current_version_stmt)).scalar_one_or_none()
                    reusable_snapshot_doc: Optional[Document] = None
                    if current_version and current_version.raw_html_document_id:
                        reusable_snapshot_doc = await session.get(Document, current_version.raw_html_document_id)
                    if current_version:
                        current_version.is_current = False
                        # 仅保留最新版本快照：历史版本不再持有 raw_html 引用。
                        current_version.raw_html_document_id = None

                    next_version_no = int(
                        await session.scalar(
                            select(func.coalesce(func.max(KBWebPageVersion.version_no), 0)).where(
                                KBWebPageVersion.kb_web_page_id == page.id
                            )
                        )
                        or 0
                    ) + 1

                    raw_html_document_id = await _persist_raw_html_snapshot_document(
                        session=session,
                        page=page,
                        run=run,
                        source_document=document,
                        raw_html=raw_html,
                        existing_snapshot_doc=reusable_snapshot_doc,
                    )

                    version = KBWebPageVersion(
                        tenant_id=page.tenant_id,
                        kb_id=page.kb_id,
                        kb_web_page_id=page.id,
                        kb_doc_id=page.kb_doc_id,
                        document_id=page.document_id,
                        version_no=next_version_no,
                        is_current=True,
                        is_material_change=True,
                        trigger_type=run.trigger_type,
                        fetch_started_at=started_at,
                        fetch_ended_at=now,
                        fetch_status="success",
                        http_status=http_status,
                        final_url=final_url,
                        canonical_url=page.canonical_url,
                        title=page.title,
                        site_name=page.site_name,
                        extractor=extractor if extractor in {"trafilatura", "readability", "playwright", "custom"} else "custom",
                        raw_html_document_id=raw_html_document_id,
                        markdown_document_id=None,
                        content_text=extracted,
                        content_hash=new_hash,
                        text_length=len(extracted),
                        change_summary=None,
                        diff_from_version_id=page.last_success_version_id,
                        chunk_status="queued",
                        chunk_count=0,
                        extra_metadata={
                            "quality_summary": quality_summary,
                            "structured_sections": structured_sections,
                            "fetch_mode": page.fetch_mode,
                            "final_url": final_url,
                        },
                        created_by_id=run.triggered_by_id,
                        created_by_name=run.triggered_by_name,
                        updated_by_id=run.triggered_by_id,
                        updated_by_name=run.triggered_by_name,
                    )
                    session.add(version)
                    await session.flush()
                    version_id = version.id

                    # 更新页面和版本相关的元数据
                    version.chunk_status = "queued"
                    version.chunk_count = 0
                    page.last_success_version_id = version.id
                    page.last_content_changed_at = now
                    page.latest_content_hash = new_hash

                should_dispatch_parse = bool(content_changed or force_rebuild_index)
                if should_dispatch_parse:
                    chunks_after = None
                    parse_signature = await prepare_parse_pipeline_submission(
                        session,
                        kb_doc,
                        reset_chunk_count=False,
                        effective_config=build_effective_config(kb_doc, kb=kb),
                    )
                    await sync_latest_attempt_snapshot(
                        session,
                        kb_doc,
                        trigger_source="web_sync",
                        status="processing",
                        runtime_stage="syncing",
                        task_id=None,
                        config_snapshot={
                            "web_sync": {
                                "force_rebuild_index": force_rebuild_index,
                                "rebuild_policy": (
                                    "always_rebuild"
                                    if force_rebuild_index
                                    else "content_changed_only"
                                ),
                            }
                        },
                        stats={
                            "content_changed": content_changed,
                            "http_status": http_status,
                            "text_length": len(extracted),
                            "quality_summary": quality_summary,
                        },
                    )
                    _append_run_log(
                        run,
                        level="info",
                        stage="pipeline",
                        message=(
                            "网页内容有变化，已提交统一解析链"
                            if content_changed
                            else "已启用“始终重建索引”，内容未变化也会提交统一解析链"
                        ),
                        detail={
                            "content_changed": content_changed,
                            "force_rebuild_index": force_rebuild_index,
                            "version_id": str(version_id) if version_id else None,
                            "quality_summary": quality_summary,
                        },
                    )
                    logger.info(
                        "[WebSyncRun] 网页同步成功，准备提交统一 Parse 流程: kb_doc=%s, version_id=%s, content_changed=%s, force_rebuild_index=%s, text_length=%s",
                        kb_doc.id,
                        version_id,
                        content_changed,
                        force_rebuild_index,
                        len(extracted),
                    )
                else:
                    kb_doc.parse_status = "completed"
                    kb_doc.parse_error = None
                    kb_doc.task_id = None
                    kb_doc.parse_progress = 100
                    kb_doc.parse_started_at = started_at
                    kb_doc.parse_ended_at = now
                    kb_doc.parse_duration_milliseconds = int((now - started_at).total_seconds() * 1000)
                    set_runtime_stage(kb_doc, "completed")

                    await add_log(session, kb_doc, "INIT", "网页同步完成，开始评估是否需要重建索引...", "processing")
                    await sync_latest_attempt_snapshot(
                        session,
                        kb_doc,
                        trigger_source="web_sync",
                        status="processing",
                        runtime_stage="syncing",
                        task_id=None,
                        config_snapshot={
                            "web_sync": {
                                "force_rebuild_index": False,
                                "rebuild_policy": "content_changed_only",
                            }
                        },
                        stats={
                            "content_changed": False,
                            "http_status": http_status,
                            "text_length": len(extracted),
                            "quality_summary": quality_summary,
                        },
                    )
                    await add_log(session, kb_doc, "WEB_SYNC", "网页抓取成功，正文内容未发生变化", "done")
                    await add_log(
                        session,
                        kb_doc,
                        "SKIP",
                        "当前策略为“仅内容变化时重建”，已跳过 parse -> chunk -> enhance -> train",
                        "done",
                    )
                    await sync_latest_attempt_snapshot(
                        session,
                        kb_doc,
                        trigger_source="web_sync",
                        status="completed",
                        runtime_stage="completed",
                        task_id=None,
                        error_message=None,
                        config_snapshot={
                            "web_sync": {
                                "force_rebuild_index": False,
                                "rebuild_policy": "content_changed_only",
                            }
                        },
                        stats={
                            "content_changed": False,
                            "http_status": http_status,
                            "text_length": len(extracted),
                            "chunk_count": int(kb_doc.chunk_count or 0),
                            "quality_summary": quality_summary,
                        },
                    )
                    await finalize_latest_attempt(
                        session,
                        kb_doc.id,
                        final_status="completed",
                        duration_ms=kb_doc.parse_duration_milliseconds,
                    )
                    _append_run_log(
                        run,
                        level="info",
                        stage="skip",
                        message="网页内容未变化，已跳过统一解析链",
                        detail={
                            "content_changed": False,
                            "force_rebuild_index": False,
                            "skip_pipeline": True,
                            "quality_summary": quality_summary,
                        },
                    )

                run.status = "success"
                run.ended_at = now
                run.duration_ms = int((now - started_at).total_seconds() * 1000)
                run.http_status = http_status
                run.content_changed = content_changed
                run.old_content_hash = old_hash
                run.new_content_hash = new_hash
                run.chunks_before = chunks_before
                run.chunks_after = chunks_after
                run.version_id = version_id
                await session.commit()
                if parse_signature is not None:
                    dispatch_parse_pipeline(parse_signature)
                return {
                    "status": "success",
                    "run_id": str(run.id),
                    "content_changed": content_changed,
                    "chunks_after": chunks_after,
                }
            except Exception as exc:  # noqa: BLE001
                # 兜底失败落库，确保运行态不会卡死在 running。
                failed_at = _now_utc()
                timeout = int((page.config_json or {}).get("timeout_seconds") or 20)
                error_message, error_detail = _build_web_sync_error_message(
                    page=page,
                    exc=exc,
                    stage="extract_web_content",
                    timeout_seconds=timeout,
                )
                logger.error(
                    "[WebSyncRun] 同步失败并落库: run=%s, url=%s, stage=%s, err=%s",
                    run.id,
                    page.url,
                    error_detail.get("stage"),
                    error_message,
                    exc_info=True,
                )
                run.status = "failed"
                run.ended_at = failed_at
                run.duration_ms = int((failed_at - started_at).total_seconds() * 1000)
                run.error_message = error_message
                run.logs_json = list(run.logs_json or []) + [{
                    "time": failed_at.isoformat(),
                    "level": "error",
                    "stage": error_detail.get("stage"),
                    "message": error_message,
                    "detail": error_detail,
                }]
                page.sync_status = "failed"
                page.last_error = error_message
                kb_doc.parse_status = "failed"
                kb_doc.runtime_stage = "failed"
                kb_doc.runtime_updated_at = failed_at
                kb_doc.parse_error = error_message
                kb_doc.parse_ended_at = failed_at
                await session.commit()
                return {
                    "status": "failed",
                    "run_id": str(run.id),
                    "error": error_message,
                }
            finally:
                await _release_lock(redis_client, page_lock_key, page_lock_token)
    finally:
        await close_task_redis_client(redis_client)
        await close_task_db_engine(task_engine)


async def _cleanup_web_page_versions(
    *,
    max_versions_per_page: int = 20,
    retention_days: int = 180,
    page_batch_size: int = 200,
) -> dict:
    """
    清理网页历史版本（保留当前版本 + 最近 N 条 + 近 T 天）。

    说明：
    - 不影响 current 版本；
    - 删除版本后尝试清理无引用的网页快照文档（raw_html / markdown）。
    """
    task_engine, task_sm = create_task_session_maker()
    deleted_versions = 0
    deleted_documents = 0
    touched_pages = 0
    now = _now_utc()
    cutoff = now - timedelta(days=max(1, int(retention_days or 180)))
    keep_n = max(1, int(max_versions_per_page or 20))

    try:
        async with task_sm() as session:
            page_ids = (
                await session.execute(
                    select(KBWebPage.id)
                    .order_by(KBWebPage.updated_at.desc())
                    .limit(max(1, int(page_batch_size or 200)))
                )
            ).scalars().all()

            for page_id in page_ids:
                versions = (
                    await session.execute(
                        select(KBWebPageVersion)
                        .where(KBWebPageVersion.kb_web_page_id == page_id)
                        .order_by(KBWebPageVersion.created_at.desc())
                    )
                ).scalars().all()
                if not versions:
                    continue

                touched_pages += 1
                keep_ids: set[UUID] = set()

                # 1) 永远保留 current 版本
                for version in versions:
                    if bool(version.is_current):
                        keep_ids.add(version.id)

                # 2) 保留最近 N 条
                for version in versions[:keep_n]:
                    keep_ids.add(version.id)

                # 3) 保留近 T 天版本
                for version in versions:
                    created_at = version.created_at
                    if created_at and created_at >= cutoff:
                        keep_ids.add(version.id)

                delete_candidates = [version for version in versions if version.id not in keep_ids]
                if not delete_candidates:
                    continue

                candidate_raw_doc_ids = {
                    version.raw_html_document_id
                    for version in delete_candidates
                    if version.raw_html_document_id is not None
                }
                candidate_md_doc_ids = {
                    version.markdown_document_id
                    for version in delete_candidates
                    if version.markdown_document_id is not None
                }
                candidate_doc_ids = set(candidate_raw_doc_ids) | set(candidate_md_doc_ids)

                delete_ids = [version.id for version in delete_candidates]
                await session.execute(
                    delete(KBWebPageVersion).where(KBWebPageVersion.id.in_(delete_ids))
                )
                deleted_versions += len(delete_ids)

                # 清理无引用快照文档（仅系统生成快照）。
                for doc_id in candidate_doc_ids:
                    remains_raw_ref = await session.scalar(
                        select(func.count())
                        .select_from(KBWebPageVersion)
                        .where(KBWebPageVersion.raw_html_document_id == doc_id)
                    )
                    remains_md_ref = await session.scalar(
                        select(func.count())
                        .select_from(KBWebPageVersion)
                        .where(KBWebPageVersion.markdown_document_id == doc_id)
                    )
                    if int(remains_raw_ref or 0) > 0 or int(remains_md_ref or 0) > 0:
                        continue

                    doc = await session.get(Document, doc_id)
                    if not doc:
                        continue

                    # 只清理系统生成的虚拟快照，避免误删业务文档。
                    if not (
                        doc.carrier_type == "generated_snapshot"
                        and doc.asset_kind == "virtual"
                        and doc.source_type == "system"
                    ):
                        continue

                    await session.execute(delete(Document).where(Document.id == doc_id))
                    deleted_documents += 1

            await session.commit()

        return {
            "status": "success",
            "touched_pages": touched_pages,
            "deleted_versions": deleted_versions,
            "deleted_documents": deleted_documents,
            "retention_days": retention_days,
            "max_versions_per_page": max_versions_per_page,
        }
    finally:
        await close_task_db_engine(task_engine)


@celery_app.task(
    name="tasks.web_sync.dispatch_due_web_sync_jobs_task",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def dispatch_due_web_sync_jobs_task(self, batch_size: int = 100):
    """动态分发到期网页同步任务。"""
    async def _run():
        return await _dispatch_due_web_sync_jobs(batch_size=batch_size)

    try:
        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        logger.error("[WebSyncDispatch] 分发失败: %s", exc, exc_info=True)
        if self.request.retries >= self.max_retries:
            return {"status": "failed", "error": str(exc)}
        is_timeout = isinstance(exc, (redis_exc.TimeoutError, redis_exc.ConnectionError, TimeoutError))
        countdown = min(60, 10 * (2 ** self.request.retries)) if is_timeout else (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(
    name="tasks.web_sync.execute_web_sync_run_task",
    bind=True,
    soft_time_limit=300,
    time_limit=360,
    acks_late=True,
)
def execute_web_sync_run_task(self, run_id: str):
    """执行单次网页同步任务。"""
    async def _run():
        return await _execute_web_sync_run(UUID(run_id))

    try:
        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        logger.error("[WebSyncRun] 执行失败: run=%s, err=%s", run_id, exc, exc_info=True)
        return {"status": "failed", "run_id": run_id, "error": str(exc)}


@celery_app.task(
    name="tasks.web_sync.cleanup_web_page_versions_task",
    bind=True,
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def cleanup_web_page_versions_task(
    self,
    max_versions_per_page: int = 20,
    retention_days: int = 180,
    page_batch_size: int = 200,
):
    """定时清理网页历史版本与孤儿快照文档。"""

    async def _run():
        return await _cleanup_web_page_versions(
            max_versions_per_page=max_versions_per_page,
            retention_days=retention_days,
            page_batch_size=page_batch_size,
        )

    try:
        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        logger.error("[WebSyncCleanup] 清理失败: %s", exc, exc_info=True)
        if self.request.retries >= self.max_retries:
            return {"status": "failed", "error": str(exc)}
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
