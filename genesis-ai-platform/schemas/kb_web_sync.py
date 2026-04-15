"""
网页同步 Schema 定义
"""
from datetime import date, datetime, time
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class WebPageCreateRequest(BaseModel):
    """新增网页资源请求。"""

    kb_id: UUID
    url: str = Field(..., min_length=1)
    folder_id: Optional[UUID] = None
    display_name: Optional[str] = None
    fetch_mode: str = Field(default="auto")
    page_config: dict[str, Any] = Field(default_factory=dict)
    trigger_sync_now: bool = Field(default=False, description="是否创建后立即触发同步")

    @field_validator("fetch_mode")
    @classmethod
    def validate_fetch_mode(cls, value: str) -> str:
        if value not in {"auto", "static", "browser"}:
            raise ValueError("fetch_mode 必须是 auto/static/browser")
        return value


class WebPageListRequest(BaseModel):
    """网页资源列表请求。"""

    kb_id: UUID
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    search: Optional[str] = None
    sync_status: Optional[str] = None
    folder_id: Optional[UUID] = None
    include_subfolders: bool = Field(default=False, description="是否包含子文件夹")


class WebPageUpdateRequest(BaseModel):
    """更新网页资源请求。"""

    kb_web_page_id: UUID
    url: Optional[str] = Field(default=None, min_length=1)
    display_name: Optional[str] = None
    # folder_id 为 None 表示不修改；传 "__root__" 特殊值表示移动到根目录（folder_id 置空）
    folder_id: Optional[str] = Field(default=None, description="目标文件夹ID，传 '__root__' 表示移动到根目录，None 表示不变更目录")
    fetch_mode: Optional[str] = Field(default=None)
    page_config: Optional[dict[str, Any]] = None

    @field_validator("fetch_mode")
    @classmethod
    def validate_fetch_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if value not in {"auto", "static", "browser"}:
            raise ValueError("fetch_mode 必须是 auto/static/browser")
        return value


class WebPageToggleRequest(BaseModel):
    """网页资源启停请求。"""

    kb_web_page_id: UUID
    is_enabled: bool


class WebPagePreviewRequest(BaseModel):
    """网页抽取预览请求。"""

    kb_web_page_id: UUID
    content_selector: Optional[str] = None
    fetch_mode: Optional[str] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=5, le=120)
    include_raw_html: bool = True

    @field_validator("fetch_mode")
    @classmethod
    def validate_fetch_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if value not in {"auto", "static", "browser"}:
            raise ValueError("fetch_mode 必须是 auto/static/browser")
        return value


class WebScheduleCreateRequest(BaseModel):
    """创建调度规则请求。"""

    kb_id: UUID
    kb_web_page_id: Optional[UUID] = None
    scope_level: str = Field(default="kb_default")
    schedule_type: str = Field(default="manual")
    cron_expr: Optional[str] = None
    timezone: str = Field(default="Asia/Shanghai")
    interval_value: Optional[int] = None
    interval_unit: Optional[str] = None
    run_time: Optional[time] = None
    run_date: Optional[date] = None
    weekdays: list[int] = Field(default_factory=list)
    monthdays: list[int] = Field(default_factory=list)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    priority: int = 100
    is_enabled: bool = True
    jitter_seconds: int = 0
    extra_metadata: dict[str, Any] = Field(default_factory=dict)


class WebScheduleUpdateRequest(BaseModel):
    """更新调度规则请求。"""

    schedule_id: UUID
    schedule_type: Optional[str] = None
    cron_expr: Optional[str] = None
    timezone: Optional[str] = None
    interval_value: Optional[int] = None
    interval_unit: Optional[str] = None
    run_time: Optional[time] = None
    run_date: Optional[date] = None
    weekdays: Optional[list[int]] = None
    monthdays: Optional[list[int]] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    priority: Optional[int] = None
    is_enabled: Optional[bool] = None
    jitter_seconds: Optional[int] = None
    extra_metadata: Optional[dict[str, Any]] = None


class WebScheduleListRequest(BaseModel):
    """调度规则列表请求。"""

    kb_id: UUID
    kb_web_page_id: Optional[UUID] = None


class WebScheduleDeleteRequest(BaseModel):
    """删除调度规则请求。"""

    schedule_id: UUID


class WebSyncNowRequest(BaseModel):
    """立即同步请求。"""

    kb_web_page_id: UUID
    force_rebuild_index: bool = Field(default=False, description="是否忽略内容变化检查并始终重建索引")


class WebSyncNowByKBDocRequest(BaseModel):
    """按知识库文档ID立即同步请求。"""

    kb_doc_id: UUID
    force_rebuild_index: bool = Field(default=False, description="是否忽略内容变化检查并始终重建索引")


class WebLatestCheckRequest(BaseModel):
    """最新性校验请求。"""

    kb_web_page_id: UUID


class WebSyncRunListRequest(BaseModel):
    """同步运行记录列表请求。"""

    kb_id: UUID
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    kb_web_page_id: Optional[UUID] = None
    status: Optional[str] = None
