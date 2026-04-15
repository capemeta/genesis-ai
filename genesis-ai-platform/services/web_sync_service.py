"""
网页同步服务

负责：
- 网页资源创建与列表
- 调度规则创建/更新/查询
- 立即同步触发（仅入队记录）
- 运行记录查询
"""
import hashlib
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse
from uuid import UUID as PyUUID, uuid4

from croniter import croniter  # type: ignore[import-untyped]
from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.document import Document
from models.folder import Folder
from models.kb_web_page import KBWebPage
from models.kb_web_page_version import KBWebPageVersion
from models.kb_web_sync_run import KBWebSyncRun
from models.kb_web_sync_schedule import KBWebSyncSchedule
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.user import User
from services.web_content_extractor import extract_web_content


class WebSyncService:
    """网页同步服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _extract_quality_summary_from_logs(self, logs_json: Any) -> Optional[dict[str, Any]]:
        """从运行日志中提取最新的抽取质量摘要。"""
        entries = list(logs_json or [])
        for entry in reversed(entries):
            if not isinstance(entry, dict):
                continue
            detail = dict(entry.get("detail") or {})
            quality_summary = detail.get("quality_summary")
            if isinstance(quality_summary, dict):
                return quality_summary
        return None

    def _count_selector_matches(self, html: str, selector: Optional[str]) -> dict[str, Any]:
        """统计 CSS 选择器命中情况，供前端预览弹窗展示。"""
        normalized_selector = str(selector or "").strip()
        if not normalized_selector:
            return {
                "requested_selector": "",
                "matched_count": 0,
                "applied": False,
                "valid": True,
                "reason": "selector_empty",
            }
        try:
            from lxml import html as lxml_html  # type: ignore[import-untyped]

            root = lxml_html.fromstring(html or "")
            matches = root.cssselect(normalized_selector)
            return {
                "requested_selector": normalized_selector,
                "matched_count": len(matches),
                "applied": bool(matches),
                "valid": True,
                "reason": "matched" if matches else "not_matched",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "requested_selector": normalized_selector,
                "matched_count": 0,
                "applied": False,
                "valid": False,
                "reason": "invalid_selector",
                "error": str(exc)[:300],
            }

    def _build_default_page_config(self, page_config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """构建网页页面默认配置，统一承载抓取与分块参数。"""
        raw_config = dict(page_config or {})
        chunking_config = dict(raw_config.get("chunking_config") or {})
        normalized_config = {
            **raw_config,
            "timeout_seconds": max(5, int(raw_config.get("timeout_seconds") or 20)),
            "chunking_config": {
                "max_embed_tokens": max(128, int(chunking_config.get("max_embed_tokens") or 512)),
            },
        }
        content_selector = str(raw_config.get("content_selector") or "").strip()
        if content_selector:
            normalized_config["content_selector"] = content_selector
        else:
            normalized_config.pop("content_selector", None)
        return normalized_config

    async def create_page(
        self,
        *,
        kb_id: PyUUID,
        url: str,
        current_user: User,
        folder_id: Optional[PyUUID] = None,
        display_name: Optional[str] = None,
        fetch_mode: str = "auto",
        page_config: Optional[dict[str, Any]] = None,
        trigger_sync_now: bool = False,
    ) -> dict[str, Any]:
        """创建网页资源（documents + knowledge_base_documents + kb_web_pages）。"""
        kb = await self._get_web_kb_for_user(kb_id, current_user)
        normalized_url = self._normalize_url(url)
        parsed = urlparse(normalized_url)
        domain = parsed.netloc.lower()

        exists_stmt = select(KBWebPage).where(
            KBWebPage.tenant_id == current_user.tenant_id,
            KBWebPage.kb_id == kb.id,
            KBWebPage.normalized_url == normalized_url,
        )
        exists = (await self.session.execute(exists_stmt)).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该 URL 已存在于当前知识库")

        # 使用 URL 哈希构造稳定 file_key，便于后续定位与排查。
        url_hash = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
        file_key = f"remote/web/{kb.id}/{url_hash}"

        now = datetime.now(timezone.utc)
        document_name = self._build_page_display_name(display_name=display_name, domain=domain, url=normalized_url)
        document = Document(
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
            name=document_name,
            file_type="HTML",
            storage_driver="local",
            bucket_name=None,
            file_key=file_key,
            file_size=0,
            mime_type="text/html",
            carrier_type="web_page",
            asset_kind="remote",
            source_type="crawl",
            source_url=normalized_url,
            content_hash=None,
            metadata_info={
                "domain": domain,
                "normalized_url": normalized_url,
                "content_kind": "web_page",
            },
            created_by_id=current_user.id,
            created_by_name=current_user.nickname,
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname,
            created_at=now,
            updated_at=now,
        )
        self.session.add(document)
        await self.session.flush()

        kb_doc = KnowledgeBaseDocument(
            tenant_id=current_user.tenant_id,
            kb_id=kb.id,
            document_id=document.id,
            folder_id=folder_id,
            display_name=document_name,
            owner_id=current_user.id,
            parse_status="pending",
            parse_error=None,
            parse_progress=0,
            chunk_count=0,
            summary=None,
            custom_metadata={"content_kind": "web_page", "source_mode": "crawl"},
            parse_config={"strategy": "web"},
            chunking_config={"chunk_strategy": "web_page", "chunk_size": 800, "overlap": 120},
            intelligence_config={},
            runtime_stage="pending",
            runtime_updated_at=now,
            parse_started_at=None,
            parse_ended_at=None,
            parse_duration_milliseconds=0,
            task_id=None,
            markdown_document_id=None,
            display_order=0,
            is_enabled=True,
            created_by_id=current_user.id,
            created_by_name=current_user.nickname,
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname,
            created_at=now,
            updated_at=now,
        )
        self.session.add(kb_doc)
        await self.session.flush()

        web_page = KBWebPage(
            tenant_id=current_user.tenant_id,
            kb_id=kb.id,
            document_id=document.id,
            kb_doc_id=kb_doc.id,
            folder_id=folder_id,
            url=normalized_url,
            normalized_url=normalized_url,
            canonical_url=None,
            domain=domain,
            title=document_name if display_name else None,
            site_name=domain,
            source_type="manual",
            fetch_mode=fetch_mode,
            sync_status="idle",
            content_status="new",
            last_success_version_id=None,
            last_synced_at=None,
            last_content_changed_at=None,
            next_sync_at=None,
            last_checked_at=None,
            last_check_status=None,
            last_error=None,
            last_http_status=None,
            etag=None,
            last_modified=None,
            latest_content_hash=None,
            config_json=self._build_default_page_config(page_config),
            extra_metadata={},
            is_enabled=True,
            created_by_id=current_user.id,
            created_by_name=current_user.nickname,
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname,
            created_at=now,
            updated_at=now,
        )
        self.session.add(web_page)
        await self.session.flush()

        queued_run_id: Optional[str] = None
        if trigger_sync_now:
            run = await self._queue_manual_sync(web_page=web_page, kb_doc=kb_doc, current_user=current_user)
            queued_run_id = str(run.id)

        await self.session.commit()
        if queued_run_id:
            # 提交后再投递，避免任务先执行时读不到 run 记录。
            from tasks.web_sync_tasks import execute_web_sync_run_task

            execute_web_sync_run_task.delay(queued_run_id)
        return {
            "kb_web_page_id": str(web_page.id),
            "kb_doc_id": str(kb_doc.id),
            "document_id": str(document.id),
            "name": document.name,
            "url": web_page.url,
            "normalized_url": web_page.normalized_url,
            "domain": web_page.domain,
            "fetch_mode": web_page.fetch_mode,
            "page_config": dict(web_page.config_json or {}),
            "sync_status": web_page.sync_status,
            "queued_run_id": queued_run_id,
        }

    async def list_pages(
        self,
        *,
        kb_id: PyUUID,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        sync_status: Optional[str] = None,
        folder_id: Optional[PyUUID] = None,
        include_subfolders: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """分页查询网页资源列表。"""
        await self._get_web_kb_for_user(kb_id, current_user)

        stmt = (
            select(KBWebPage, KnowledgeBaseDocument, Document)
            .join(KnowledgeBaseDocument, KBWebPage.kb_doc_id == KnowledgeBaseDocument.id)
            .join(Document, KBWebPage.document_id == Document.id)
            .where(
                KBWebPage.tenant_id == current_user.tenant_id,
                KBWebPage.kb_id == kb_id,
            )
        )

        if folder_id:
            if include_subfolders:
                folder_stmt = select(Folder.path).where(
                    Folder.id == folder_id,
                    Folder.tenant_id == current_user.tenant_id,
                    Folder.kb_id == kb_id,
                )
                folder_path = (await self.session.execute(folder_stmt)).scalar_one_or_none()
                if not folder_path:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件夹不存在")

                subfolder_stmt = select(Folder.id).where(
                    Folder.tenant_id == current_user.tenant_id,
                    Folder.kb_id == kb_id,
                    text(f"path <@ '{folder_path}'::ltree"),
                )
                subfolder_ids = [row[0] for row in (await self.session.execute(subfolder_stmt)).all()]
                if subfolder_ids:
                    stmt = stmt.where(KnowledgeBaseDocument.folder_id.in_(subfolder_ids))
                else:
                    stmt = stmt.where(KnowledgeBaseDocument.folder_id == folder_id)
            else:
                stmt = stmt.where(KnowledgeBaseDocument.folder_id == folder_id)
        elif not include_subfolders:
            # 与文件列表保持一致：未选中文件夹且未勾选包含子文件夹时，仅查看根目录页面。
            stmt = stmt.where(KnowledgeBaseDocument.folder_id.is_(None))
        if sync_status:
            stmt = stmt.where(KBWebPage.sync_status == sync_status)
        normalized_search = str(search or "").strip()
        if normalized_search:
            like_value = f"%{normalized_search}%"
            stmt = stmt.where(
                (Document.name.ilike(like_value))
                | (KBWebPage.url.ilike(like_value))
                | (KBWebPage.domain.ilike(like_value))
                | (KBWebPage.title.ilike(like_value))
            )

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(await self.session.scalar(total_stmt) or 0)

        stmt = (
            stmt.order_by(KBWebPage.updated_at.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(stmt)).all()

        data: list[dict[str, Any]] = []
        for web_page, kb_doc, document in rows:
            data.append(
                {
                    "kb_web_page_id": str(web_page.id),
                    "kb_doc_id": str(kb_doc.id),
                    "document_id": str(document.id),
                    "name": kb_doc.display_name or document.name,
                    "url": web_page.url,
                    "domain": web_page.domain,
                    "fetch_mode": web_page.fetch_mode,
                    "page_config": dict(web_page.config_json or {}),
                    "sync_status": web_page.sync_status,
                    "content_status": web_page.content_status,
                    "last_synced_at": web_page.last_synced_at.isoformat() if web_page.last_synced_at else None,
                    "last_content_changed_at": (
                        web_page.last_content_changed_at.isoformat() if web_page.last_content_changed_at else None
                    ),
                    "next_sync_at": web_page.next_sync_at.isoformat() if web_page.next_sync_at else None,
                    "last_checked_at": web_page.last_checked_at.isoformat() if web_page.last_checked_at else None,
                    "last_check_status": web_page.last_check_status,
                    "chunk_count": int(kb_doc.chunk_count or 0),
                    "parse_status": kb_doc.parse_status,
                    # 同步失败时的错误信息（与 kb_doc.parse_error 内容相同，便于 web 工作台视图直接使用）
                    "last_error": web_page.last_error,
                    "is_enabled": bool(kb_doc.is_enabled and web_page.is_enabled),
                    "folder_id": str(kb_doc.folder_id) if kb_doc.folder_id else None,
                    "created_at": web_page.created_at.isoformat() if web_page.created_at else None,
                }
            )
        return data, total

    async def toggle_page_enabled(
        self,
        *,
        kb_web_page_id: PyUUID,
        is_enabled: bool,
        current_user: User,
    ) -> dict[str, Any]:
        """启停网页资源。"""
        web_page, kb_doc = await self._get_page_with_kb_doc(kb_web_page_id, current_user)
        now = datetime.now(timezone.utc)

        web_page.is_enabled = is_enabled
        kb_doc.is_enabled = is_enabled
        web_page.updated_by_id = current_user.id
        web_page.updated_by_name = current_user.nickname
        web_page.updated_at = now
        kb_doc.updated_by_id = current_user.id
        kb_doc.updated_by_name = current_user.nickname
        kb_doc.updated_at = now
        await self.session.commit()
        return {
            "kb_web_page_id": str(web_page.id),
            "kb_doc_id": str(kb_doc.id),
            "is_enabled": is_enabled,
        }

    async def update_page(
        self,
        *,
        kb_web_page_id: PyUUID,
        current_user: User,
        url: Optional[str] = None,
        display_name: Optional[str] = None,
        folder_id: Optional[str] = None,
        fetch_mode: Optional[str] = None,
        page_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """更新网页资源（标题/URL/归属目录）。"""
        stmt = (
            select(KBWebPage, KnowledgeBaseDocument, Document)
            .join(KnowledgeBaseDocument, KBWebPage.kb_doc_id == KnowledgeBaseDocument.id)
            .join(Document, KBWebPage.document_id == Document.id)
            .where(
                KBWebPage.id == kb_web_page_id,
                KBWebPage.tenant_id == current_user.tenant_id,
            )
        )
        row = (await self.session.execute(stmt)).first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="网页资源不存在")

        web_page, kb_doc, document = row
        now = datetime.now(timezone.utc)

        # URL 更新后会影响域名与去重键，需要同步刷新关联字段。
        url_changed = False
        if url is not None and str(url).strip():
            normalized_url = self._normalize_url(url)
            if normalized_url != web_page.normalized_url:
                exists_stmt = select(KBWebPage.id).where(
                    KBWebPage.tenant_id == current_user.tenant_id,
                    KBWebPage.kb_id == web_page.kb_id,
                    KBWebPage.normalized_url == normalized_url,
                    KBWebPage.id != web_page.id,
                )
                duplicated = (await self.session.execute(exists_stmt)).scalar_one_or_none()
                if duplicated:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该 URL 已存在于当前知识库")

                parsed = urlparse(normalized_url)
                domain = parsed.netloc.lower()
                url_hash = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()

                web_page.url = normalized_url
                web_page.normalized_url = normalized_url
                web_page.domain = domain
                web_page.site_name = domain
                web_page.last_checked_at = None
                web_page.last_check_status = None
                web_page.last_http_status = None
                web_page.last_error = None
                document.source_url = normalized_url
                document.file_key = f"remote/web/{web_page.kb_id}/{url_hash}"

                metadata_info = dict(document.metadata_info or {})
                metadata_info["domain"] = domain
                metadata_info["normalized_url"] = normalized_url
                document.metadata_info = metadata_info
                url_changed = True

        if display_name is not None:
            normalized_name = str(display_name).strip()
            if not normalized_name:
                normalized_name = self._build_page_display_name(
                    display_name=None,
                    domain=str(web_page.domain or ""),
                    url=web_page.url,
                )
            kb_doc.display_name = normalized_name
            document.name = normalized_name
            web_page.title = normalized_name

        if fetch_mode is not None:
            web_page.fetch_mode = fetch_mode

        if page_config is not None:
            web_page.config_json = self._build_default_page_config(page_config)

        # folder_id 为 None 表示不变更目录；传 "__root__" 表示移动到根目录，其他字符串则解析为 UUID。
        if folder_id is not None:
            if folder_id == "__root__":
                # 移动到根目录
                kb_doc.folder_id = None
                web_page.folder_id = None
            else:
                # 请求带来了具体 folder_id，需要校验属于该知识库
                from uuid import UUID as StdUUID
                try:
                    target_folder_id = StdUUID(folder_id)
                except ValueError as exc:
                    from fastapi import HTTPException
                    raise HTTPException(status_code=400, detail="folder_id 格式错误") from exc

                folder_stmt = select(Folder.id).where(
                    Folder.id == target_folder_id,
                    Folder.tenant_id == current_user.tenant_id,
                    Folder.kb_id == web_page.kb_id,
                )
                exists = (await self.session.execute(folder_stmt)).scalar_one_or_none()
                if not exists:
                    from fastapi import HTTPException
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标文件夹不存在")

                kb_doc.folder_id = target_folder_id
                web_page.folder_id = target_folder_id

        if url_changed:
            # URL 发生变化后，重置状态，等待用户手动触发同步或定时任务更新内容。
            web_page.sync_status = "idle"
            web_page.content_status = "new"
            web_page.latest_content_hash = None
            web_page.last_synced_at = None
            web_page.last_content_changed_at = None
            web_page.next_sync_at = None
            web_page.last_success_version_id = None
            kb_doc.parse_status = "pending"
            kb_doc.parse_error = None
            kb_doc.parse_progress = 0
            kb_doc.runtime_stage = "pending"
            kb_doc.runtime_updated_at = now

        web_page.updated_by_id = current_user.id
        web_page.updated_by_name = current_user.nickname
        web_page.updated_at = now
        kb_doc.updated_by_id = current_user.id
        kb_doc.updated_by_name = current_user.nickname
        kb_doc.updated_at = now
        document.updated_by_id = current_user.id
        document.updated_by_name = current_user.nickname
        document.updated_at = now

        await self.session.commit()
        return {
            "kb_web_page_id": str(web_page.id),
            "kb_doc_id": str(kb_doc.id),
            "document_id": str(document.id),
            "name": kb_doc.display_name or document.name,
            "url": web_page.url,
            "domain": web_page.domain,
            "fetch_mode": web_page.fetch_mode,
            "page_config": dict(web_page.config_json or {}),
            "sync_status": web_page.sync_status,
            "content_status": web_page.content_status,
        }

    async def create_schedule(
        self,
        *,
        payload: dict[str, Any],
        current_user: User,
    ) -> dict[str, Any]:
        """创建网页同步调度规则。"""
        kb = await self._get_web_kb_for_user(payload["kb_id"], current_user)
        kb_web_page_id = payload.get("kb_web_page_id")
        scope_level = str(payload.get("scope_level") or "kb_default")
        if scope_level == "page_override" and not kb_web_page_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="页面级调度规则必须提供 kb_web_page_id")

        if kb_web_page_id:
            await self._ensure_page_in_kb(kb_web_page_id=kb_web_page_id, kb_id=kb.id, current_user=current_user)

        existing_schedule = await self._find_schedule_by_scope(
            kb_id=kb.id,
            tenant_id=current_user.tenant_id,
            scope_level=scope_level,
            kb_web_page_id=kb_web_page_id,
        )
        now = datetime.now(timezone.utc)

        if existing_schedule:
            self._apply_schedule_payload(
                schedule=existing_schedule,
                payload=payload,
                now_utc=now,
            )
            existing_schedule.updated_by_id = current_user.id
            existing_schedule.updated_by_name = current_user.nickname
            existing_schedule.updated_at = now
            schedule = existing_schedule
        else:
            schedule = KBWebSyncSchedule(
                tenant_id=current_user.tenant_id,
                kb_id=kb.id,
                kb_web_page_id=kb_web_page_id,
                scope_level=scope_level,
                created_by_id=current_user.id,
                created_by_name=current_user.nickname,
                updated_by_id=current_user.id,
                updated_by_name=current_user.nickname,
            )
            self._apply_schedule_payload(
                schedule=schedule,
                payload=payload,
                now_utc=now,
            )
            self.session.add(schedule)
        await self.session.commit()
        await self.session.refresh(schedule)
        return self._serialize_schedule(schedule)

    async def update_schedule(
        self,
        *,
        schedule_id: PyUUID,
        payload: dict[str, Any],
        current_user: User,
    ) -> dict[str, Any]:
        """更新调度规则。"""
        schedule = await self._get_schedule_for_user(schedule_id, current_user)
        now = datetime.now(timezone.utc)
        self._apply_schedule_payload(
            schedule=schedule,
            payload=payload,
            now_utc=now,
        )
        schedule.updated_by_id = current_user.id
        schedule.updated_by_name = current_user.nickname
        schedule.updated_at = now

        await self.session.commit()
        await self.session.refresh(schedule)
        return self._serialize_schedule(schedule)

    async def list_schedules(
        self,
        *,
        kb_id: PyUUID,
        current_user: User,
        kb_web_page_id: Optional[PyUUID] = None,
    ) -> list[dict[str, Any]]:
        """查询调度规则列表。"""
        await self._get_web_kb_for_user(kb_id, current_user)
        stmt = select(KBWebSyncSchedule).where(
            KBWebSyncSchedule.tenant_id == current_user.tenant_id,
            KBWebSyncSchedule.kb_id == kb_id,
        )
        if kb_web_page_id:
            stmt = stmt.where(KBWebSyncSchedule.kb_web_page_id == kb_web_page_id)
        schedules = (
            await self.session.execute(
                stmt.order_by(
                    KBWebSyncSchedule.priority.asc(),
                    KBWebSyncSchedule.updated_at.desc(),
                    KBWebSyncSchedule.created_at.desc(),
                )
            )
        ).scalars().all()

        deduped: list[KBWebSyncSchedule] = []
        seen_scope_keys: set[tuple[str, str | None]] = set()
        for item in schedules:
            scope_key = (str(item.scope_level), str(item.kb_web_page_id) if item.kb_web_page_id else None)
            if scope_key in seen_scope_keys:
                continue
            seen_scope_keys.add(scope_key)
            deduped.append(item)
        return [self._serialize_schedule(item) for item in deduped]

    async def delete_schedule(
        self,
        *,
        schedule_id: PyUUID,
        current_user: User,
    ) -> dict[str, Any]:
        """删除调度规则。"""
        schedule = await self._get_schedule_for_user(schedule_id, current_user)
        data = {
            "schedule_id": str(schedule.id),
            "kb_id": str(schedule.kb_id),
            "kb_web_page_id": str(schedule.kb_web_page_id) if schedule.kb_web_page_id else None,
            "scope_level": schedule.scope_level,
        }
        await self.session.delete(schedule)
        await self.session.commit()
        return data

    async def trigger_sync_now(
        self,
        *,
        kb_web_page_id: PyUUID,
        force_rebuild_index: bool = False,
        current_user: User,
    ) -> dict[str, Any]:
        """立即触发同步（入队记录）。"""
        web_page, kb_doc = await self._get_page_with_kb_doc(kb_web_page_id, current_user)
        run = await self._queue_manual_sync(
            web_page=web_page,
            kb_doc=kb_doc,
            current_user=current_user,
            force_rebuild_index=force_rebuild_index,
        )
        await self.session.commit()
        from tasks.web_sync_tasks import execute_web_sync_run_task

        execute_web_sync_run_task.delay(str(run.id))
        return {
            "run_id": str(run.id),
            "kb_web_page_id": str(web_page.id),
            "kb_doc_id": str(kb_doc.id),
            "status": run.status,
            "trigger_type": run.trigger_type,
            "force_rebuild_index": force_rebuild_index,
        }

    async def trigger_sync_now_by_kb_doc(
        self,
        *,
        kb_doc_id: PyUUID,
        force_rebuild_index: bool = False,
        current_user: User,
    ) -> dict[str, Any]:
        """按知识库文档ID立即触发同步（入队记录）。"""
        stmt = (
            select(KBWebPage, KnowledgeBaseDocument)
            .join(KnowledgeBaseDocument, KBWebPage.kb_doc_id == KnowledgeBaseDocument.id)
            .where(
                KBWebPage.kb_doc_id == kb_doc_id,
                KBWebPage.tenant_id == current_user.tenant_id,
            )
        )
        row = (await self.session.execute(stmt)).first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="网页资源不存在")

        web_page, kb_doc = row
        run = await self._queue_manual_sync(
            web_page=web_page,
            kb_doc=kb_doc,
            current_user=current_user,
            force_rebuild_index=force_rebuild_index,
        )
        await self.session.commit()
        from tasks.web_sync_tasks import execute_web_sync_run_task

        execute_web_sync_run_task.delay(str(run.id))
        return {
            "run_id": str(run.id),
            "kb_web_page_id": str(web_page.id),
            "kb_doc_id": str(kb_doc.id),
            "status": run.status,
            "trigger_type": run.trigger_type,
            "force_rebuild_index": force_rebuild_index,
        }

    async def latest_check(
        self,
        *,
        kb_web_page_id: PyUUID,
        current_user: User,
    ) -> dict[str, Any]:
        """执行“是否为最新版本”校验，不写入版本和分块。"""
        web_page, _ = await self._get_page_with_kb_doc(kb_web_page_id, current_user)
        timeout_seconds = int((web_page.config_json or {}).get("timeout_seconds") or 20)
        checked_at = datetime.now(timezone.utc)

        try:
            content_selector = str((web_page.config_json or {}).get("content_selector") or "").strip() or None
            result = await extract_web_content(
                url=web_page.url,
                fetch_mode=web_page.fetch_mode,
                timeout_seconds=timeout_seconds,
                content_selector=content_selector,
            )
            candidate_hash = hashlib.sha256(result.extracted_text.encode("utf-8")).hexdigest()
            latest_hash = str(web_page.latest_content_hash or "")
            if not latest_hash and web_page.last_success_version_id:
                latest_version = await self.session.get(KBWebPageVersion, web_page.last_success_version_id)
                latest_hash = str((latest_version.content_hash if latest_version else "") or "")
            is_latest = bool(latest_hash and candidate_hash == latest_hash)

            web_page.last_checked_at = checked_at
            web_page.last_check_status = "latest" if is_latest else "outdated"
            web_page.last_http_status = result.http_status
            web_page.last_error = None
            web_page.updated_by_id = current_user.id
            web_page.updated_by_name = current_user.nickname
            web_page.updated_at = checked_at
            await self.session.commit()

            if not latest_hash:
                message = "尚未同步网页内容，建议手动触发同步"
            elif is_latest:
                message = "当前版本已是最新"
            else:
                message = "检测到网页内容发生变化，可手动触发更新"

            return {
                "kb_web_page_id": str(web_page.id),
                "checked_at": checked_at.isoformat(),
                "is_latest": is_latest,
                "latest_content_hash": latest_hash or None,
                "candidate_content_hash": candidate_hash,
                "http_status": result.http_status,
                "extractor": result.extractor,
                "quality_summary": dict(result.quality_summary or {}),
                "message": message,
            }
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc)[:500]
            web_page.last_checked_at = checked_at
            web_page.last_check_status = "failed"
            web_page.last_error = error_message
            web_page.updated_by_id = current_user.id
            web_page.updated_by_name = current_user.nickname
            web_page.updated_at = checked_at
            await self.session.commit()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"校验失败: {error_message}") from exc

    async def preview_page(
        self,
        *,
        kb_web_page_id: PyUUID,
        current_user: User,
        content_selector: Optional[str] = None,
        fetch_mode: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        include_raw_html: bool = True,
    ) -> dict[str, Any]:
        """网页抽取预览，不落库，仅返回摘要和预览内容。"""
        web_page, _ = await self._get_page_with_kb_doc(kb_web_page_id, current_user)
        page_config = dict(web_page.config_json or {})
        effective_selector = str(content_selector or "").strip() or str(page_config.get("content_selector") or "").strip() or None
        effective_fetch_mode = str(fetch_mode or web_page.fetch_mode or "auto")
        effective_timeout = int(timeout_seconds or page_config.get("timeout_seconds") or 20)

        try:
            result = await extract_web_content(
                url=web_page.url,
                fetch_mode=effective_fetch_mode,
                timeout_seconds=max(5, min(120, effective_timeout)),
                content_selector=effective_selector,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("网页抓取预览失败 url=%s error=%s", web_page.url, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"网页正文抽取失败: {exc}",
            ) from exc
        selector_summary = self._count_selector_matches(result.raw_html, effective_selector)
        return {
            "kb_web_page_id": str(web_page.id),
            "url": web_page.url,
            "final_url": result.final_url,
            "fetch_mode": effective_fetch_mode,
            "timeout_seconds": max(5, min(120, effective_timeout)),
            "extractor": result.extractor,
            "http_status": result.http_status,
            "quality_summary": dict(result.quality_summary or {}),
            "selector_summary": selector_summary,
            "extracted_text": result.extracted_text,
            "extraction_html": result.extraction_html,
            "raw_html": result.extraction_html if include_raw_html else "",
            "full_page_html": result.raw_html if include_raw_html else "",
        }

    async def list_runs(
        self,
        *,
        kb_id: PyUUID,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        kb_web_page_id: Optional[PyUUID] = None,
        run_status: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """分页查询同步运行记录。"""
        await self._get_web_kb_for_user(kb_id, current_user)
        stmt = select(KBWebSyncRun).where(
            KBWebSyncRun.tenant_id == current_user.tenant_id,
            KBWebSyncRun.kb_id == kb_id,
        )
        if kb_web_page_id:
            stmt = stmt.where(KBWebSyncRun.kb_web_page_id == kb_web_page_id)
        if run_status:
            stmt = stmt.where(KBWebSyncRun.status == run_status)

        total = int(await self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        rows = (
            await self.session.execute(
                stmt.order_by(KBWebSyncRun.created_at.desc())
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        version_ids = [row.version_id for row in rows if row.version_id]
        version_quality_map: dict[PyUUID, dict[str, Any]] = {}
        if version_ids:
            version_rows = (
                await self.session.execute(
                    select(KBWebPageVersion.id, KBWebPageVersion.extra_metadata).where(
                        KBWebPageVersion.id.in_(version_ids)
                    )
                )
            ).all()
            version_quality_map = {
                version_id: dict(extra_metadata.get("quality_summary") or {})
                for version_id, extra_metadata in version_rows
                if isinstance(extra_metadata, dict)
            }

        data: list[dict[str, Any]] = []
        for row in rows:
            quality_summary = self._extract_quality_summary_from_logs(row.logs_json)
            if quality_summary is None and row.version_id:
                quality_summary = version_quality_map.get(row.version_id)
            data.append(
                {
                    "run_id": str(row.id),
                    "kb_web_page_id": str(row.kb_web_page_id),
                    "kb_doc_id": str(row.kb_doc_id),
                    "version_id": str(row.version_id) if row.version_id else None,
                    "schedule_id": str(row.schedule_id) if row.schedule_id else None,
                    "trigger_type": row.trigger_type,
                    "status": row.status,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "ended_at": row.ended_at.isoformat() if row.ended_at else None,
                    "duration_ms": row.duration_ms,
                    "http_status": row.http_status,
                    "content_changed": row.content_changed,
                    "quality_summary": quality_summary,
                    "error_message": row.error_message,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
            )
        return data, total

    async def _queue_manual_sync(
        self,
        *,
        web_page: KBWebPage,
        kb_doc: KnowledgeBaseDocument,
        current_user: User,
        force_rebuild_index: bool = False,
    ) -> KBWebSyncRun:
        """写入手动同步入队记录。"""
        running_stmt = select(KBWebSyncRun).where(
            KBWebSyncRun.kb_web_page_id == web_page.id,
            KBWebSyncRun.status.in_(["queued", "running"]),
        )
        running = (await self.session.execute(running_stmt)).scalar_one_or_none()
        if running:
            return running

        # 手动同步允许用户在短时间内重复触发。
        # 这里使用真正唯一的去重键，避免一分钟内二次点击命中唯一约束。
        dedupe_key = hashlib.sha256(
            f"{web_page.id}:manual:{force_rebuild_index}:{uuid4()}".encode("utf-8")
        ).hexdigest()

        run = KBWebSyncRun(
            tenant_id=current_user.tenant_id,
            kb_id=web_page.kb_id,
            kb_web_page_id=web_page.id,
            kb_doc_id=web_page.kb_doc_id,
            version_id=None,
            schedule_id=None,
            trigger_type="manual",
            status="queued",
            dedupe_key=dedupe_key,
            started_at=None,
            ended_at=None,
            duration_ms=None,
            http_status=None,
            content_changed=None,
            old_content_hash=web_page.latest_content_hash,
            new_content_hash=None,
            chunks_before=int(kb_doc.chunk_count or 0),
            chunks_after=None,
            error_message=None,
            logs_json=[{
                "time": datetime.now(timezone.utc).isoformat(),
                "level": "info",
                "stage": "queue",
                "message": "手动同步任务已入队",
                "detail": {
                    "force_rebuild_index": force_rebuild_index,
                    "rebuild_policy": "always" if force_rebuild_index else "content_changed_only",
                },
            }],
            triggered_by_id=current_user.id,
            triggered_by_name=current_user.nickname,
        )
        self.session.add(run)

        now = datetime.now(timezone.utc)
        web_page.sync_status = "queued"
        web_page.updated_by_id = current_user.id
        web_page.updated_by_name = current_user.nickname
        web_page.updated_at = now
        kb_doc.parse_status = "queued"
        kb_doc.runtime_stage = "queued"
        kb_doc.runtime_updated_at = now
        kb_doc.updated_by_id = current_user.id
        kb_doc.updated_by_name = current_user.nickname
        kb_doc.updated_at = now
        return run

    async def _get_web_kb_for_user(self, kb_id: PyUUID, current_user: User) -> KnowledgeBase:
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
        kb = (await self.session.execute(stmt)).scalar_one_or_none()
        if not kb:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        if kb.type != "web":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前知识库不是 web 类型")
        return kb

    async def _ensure_page_in_kb(self, *, kb_web_page_id: PyUUID, kb_id: PyUUID, current_user: User) -> None:
        stmt = select(KBWebPage.id).where(
            KBWebPage.id == kb_web_page_id,
            KBWebPage.kb_id == kb_id,
            KBWebPage.tenant_id == current_user.tenant_id,
        )
        exists = (await self.session.execute(stmt)).scalar_one_or_none()
        if not exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="网页资源不存在")

    async def _get_page_with_kb_doc(
        self, kb_web_page_id: PyUUID, current_user: User
    ) -> tuple[KBWebPage, KnowledgeBaseDocument]:
        stmt = (
            select(KBWebPage, KnowledgeBaseDocument)
            .join(KnowledgeBaseDocument, KBWebPage.kb_doc_id == KnowledgeBaseDocument.id)
            .where(
                KBWebPage.id == kb_web_page_id,
                KBWebPage.tenant_id == current_user.tenant_id,
            )
        )
        row = (await self.session.execute(stmt)).first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="网页资源不存在")
        return row[0], row[1]

    async def _get_schedule_for_user(self, schedule_id: PyUUID, current_user: User) -> KBWebSyncSchedule:
        stmt = select(KBWebSyncSchedule).where(
            KBWebSyncSchedule.id == schedule_id,
            KBWebSyncSchedule.tenant_id == current_user.tenant_id,
        )
        schedule = (await self.session.execute(stmt)).scalar_one_or_none()
        if not schedule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="调度规则不存在")
        return schedule

    async def _find_schedule_by_scope(
        self,
        *,
        kb_id: PyUUID,
        tenant_id: PyUUID,
        scope_level: str,
        kb_web_page_id: Optional[PyUUID],
    ) -> Optional[KBWebSyncSchedule]:
        """按作用域查找当前应唯一存在的调度规则。"""
        stmt = select(KBWebSyncSchedule).where(
            KBWebSyncSchedule.tenant_id == tenant_id,
            KBWebSyncSchedule.kb_id == kb_id,
            KBWebSyncSchedule.scope_level == scope_level,
        )
        if kb_web_page_id:
            stmt = stmt.where(KBWebSyncSchedule.kb_web_page_id == kb_web_page_id)
        else:
            stmt = stmt.where(KBWebSyncSchedule.kb_web_page_id.is_(None))
        stmt = stmt.order_by(KBWebSyncSchedule.updated_at.desc(), KBWebSyncSchedule.created_at.desc())
        return (await self.session.execute(stmt)).scalars().first()

    def _apply_schedule_payload(
        self,
        *,
        schedule: KBWebSyncSchedule,
        payload: dict[str, Any],
        now_utc: datetime,
    ) -> None:
        """统一写入调度字段，并清理与当前类型无关的旧字段，避免规则残留脏数据。"""
        schedule_type = str(payload.get("schedule_type") or schedule.schedule_type or "manual")
        timezone_name = str(payload.get("timezone") or schedule.timezone or "Asia/Shanghai")
        priority = int(payload.get("priority", schedule.priority or 100))
        is_enabled = bool(payload.get("is_enabled", schedule.is_enabled if schedule.is_enabled is not None else True))
        jitter_seconds = int(payload.get("jitter_seconds", schedule.jitter_seconds or 0))
        extra_metadata = dict(payload.get("extra_metadata") or schedule.extra_metadata or {})
        end_at = payload.get("end_at", schedule.end_at)
        start_at = payload.get("start_at", schedule.start_at)

        cron_expr: Optional[str] = None
        interval_value: Optional[int] = None
        interval_unit: Optional[str] = None
        run_time: Optional[time] = None
        run_date: Optional[date] = None
        weekdays: list[int] = []
        monthdays: list[int] = []

        if schedule_type == "interval":
            interval_value = payload.get("interval_value", schedule.interval_value)
            interval_unit = payload.get("interval_unit", schedule.interval_unit or "minute")
        elif schedule_type == "once":
            run_date = payload.get("run_date", schedule.run_date)
            run_time = payload.get("run_time", schedule.run_time)
        elif schedule_type == "daily":
            run_time = payload.get("run_time", schedule.run_time)
        elif schedule_type == "weekly":
            run_time = payload.get("run_time", schedule.run_time)
            weekdays = list(payload.get("weekdays") or schedule.weekdays or [])
        elif schedule_type == "monthly":
            run_time = payload.get("run_time", schedule.run_time)
            monthdays = list(payload.get("monthdays") or schedule.monthdays or [])
        elif schedule_type == "cron":
            cron_expr = payload.get("cron_expr", schedule.cron_expr)

        schedule.schedule_type = schedule_type
        schedule.timezone = timezone_name
        schedule.priority = priority
        schedule.is_enabled = is_enabled
        schedule.jitter_seconds = jitter_seconds
        schedule.extra_metadata = extra_metadata
        schedule.start_at = start_at
        schedule.end_at = end_at
        schedule.cron_expr = cron_expr
        schedule.interval_value = interval_value
        schedule.interval_unit = interval_unit
        schedule.run_time = run_time
        schedule.run_date = run_date
        schedule.weekdays = weekdays
        schedule.monthdays = monthdays
        schedule.next_trigger_at = self._compute_next_trigger_at(
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
            now_utc=now_utc,
        ) if schedule.is_enabled else None

    def _normalize_url(self, url: str) -> str:
        raw = str(url or "").strip()
        if not raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL 不能为空")
        if "://" not in raw:
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        if not parsed.netloc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL 格式不合法")
        scheme = (parsed.scheme or "https").lower()
        netloc = parsed.netloc.lower()
        normalized = parsed._replace(
            scheme=scheme,
            netloc=netloc,
            fragment="",
        )
        # 统一移除默认尾斜杠，减少重复 URL。
        path = normalized.path or "/"
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        normalized = normalized._replace(path=path)
        return urlunparse(normalized)

    def _build_page_display_name(self, *, display_name: Optional[str], domain: str, url: str) -> str:
        name = str(display_name or "").strip()
        if name:
            return name
        parsed = urlparse(url)
        path = (parsed.path or "/").strip("/")
        if path:
            return f"{domain}/{path}"
        return domain

    def _compute_next_trigger_at(
        self,
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
        """计算 next_trigger_at，统一存 UTC。"""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone_name or "Asia/Shanghai")
        now_local = now_utc.astimezone(tz)
        if start_at:
            now_local = max(now_local, start_at.astimezone(tz))

        if schedule_type == "manual":
            return None
        if schedule_type == "interval":
            if not interval_value or interval_value <= 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="interval_value 必须大于 0")
            unit = interval_unit or "minute"
            if unit == "minute":
                next_local = now_local + timedelta(minutes=interval_value)
            elif unit == "hour":
                next_local = now_local + timedelta(hours=interval_value)
            elif unit == "day":
                next_local = now_local + timedelta(days=interval_value)
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="interval_unit 必须是 minute/hour/day")
            return next_local.astimezone(timezone.utc)

        if schedule_type == "once":
            if not run_date:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="once 规则必须提供 run_date")
            scheduled_time = run_time or time(hour=0, minute=0)
            local_dt = datetime.combine(run_date, scheduled_time, tzinfo=tz)
            if local_dt <= now_local:
                return None
            return local_dt.astimezone(timezone.utc)

        if schedule_type == "daily":
            if not run_time:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="daily 规则必须提供 run_time")
            cron_text = f"{run_time.minute} {run_time.hour} * * *"
        elif schedule_type == "weekly":
            if not run_time:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="weekly 规则必须提供 run_time")
            if not weekdays:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="weekly 规则必须提供 weekdays")
            weekday_text = ",".join(str(int(day)) for day in weekdays)
            cron_text = f"{run_time.minute} {run_time.hour} * * {weekday_text}"
        elif schedule_type == "monthly":
            if not run_time:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="monthly 规则必须提供 run_time")
            if not monthdays:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="monthly 规则必须提供 monthdays")
            monthday_text = ",".join(str(int(day)) for day in monthdays)
            cron_text = f"{run_time.minute} {run_time.hour} {monthday_text} * *"
        elif schedule_type == "cron":
            if not cron_expr:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cron 规则必须提供 cron_expr")
            cron_text = cron_expr
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的 schedule_type")

        try:
            iterator = croniter(cron_text, now_local)
            next_local = iterator.get_next(datetime)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"cron 表达式不合法: {exc}") from exc
        return next_local.astimezone(timezone.utc)

    def _serialize_schedule(self, schedule: KBWebSyncSchedule) -> dict[str, Any]:
        return {
            "schedule_id": str(schedule.id),
            "kb_id": str(schedule.kb_id),
            "kb_web_page_id": str(schedule.kb_web_page_id) if schedule.kb_web_page_id else None,
            "scope_level": schedule.scope_level,
            "schedule_type": schedule.schedule_type,
            "cron_expr": schedule.cron_expr,
            "timezone": schedule.timezone,
            "interval_value": schedule.interval_value,
            "interval_unit": schedule.interval_unit,
            "run_time": schedule.run_time.isoformat() if schedule.run_time else None,
            "run_date": schedule.run_date.isoformat() if schedule.run_date else None,
            "weekdays": list(schedule.weekdays or []),
            "monthdays": list(schedule.monthdays or []),
            "start_at": schedule.start_at.isoformat() if schedule.start_at else None,
            "end_at": schedule.end_at.isoformat() if schedule.end_at else None,
            "priority": schedule.priority,
            "is_enabled": schedule.is_enabled,
            "last_triggered_at": schedule.last_triggered_at.isoformat() if schedule.last_triggered_at else None,
            "next_trigger_at": schedule.next_trigger_at.isoformat() if schedule.next_trigger_at else None,
            "jitter_seconds": schedule.jitter_seconds,
            "extra_metadata": dict(schedule.extra_metadata or {}),
        }
