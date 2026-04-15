"""
统一日志配置模块。

设计目标：
- `.env` 只配置日志根目录，代码内按用途自动拆分目录；
- 普通应用日志、常规 Celery/Task 日志、网页知识库定时任务日志分别落盘；
- 使用上下文变量保证同一条调用链里的日志进入正确文件。
"""
from __future__ import annotations

import contextvars
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Literal


LOG_CATEGORY_APP = "app"
LOG_CATEGORY_TASK = "task"
LOG_CATEGORY_WEB_SYNC = "web_sync"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOG_CATEGORY_VAR: contextvars.ContextVar[str] = contextvars.ContextVar(
    "genesis_log_category",
    default=LOG_CATEGORY_APP,
)


@dataclass(frozen=True)
class LogFilePaths:
    """日志文件路径集合。"""

    root_dir: Path
    app_log: Path
    task_log: Path
    web_sync_log: Path


class ContextEnricherFilter(logging.Filter):
    """为日志记录补充统一上下文字段。"""

    def __init__(self, process_role: str) -> None:
        super().__init__()
        self.process_role = process_role

    def filter(self, record: logging.LogRecord) -> bool:
        record.process_role = self.process_role
        record.log_category = get_log_category()
        return True


class CategoryFilter(logging.Filter):
    """仅允许指定分类的日志写入对应文件。"""

    def __init__(self, category: str) -> None:
        super().__init__()
        self.category = category

    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "log_category", get_log_category()) == self.category


class JsonFormatter(logging.Formatter):
    """轻量 JSON Formatter，避免额外依赖。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "process_role": getattr(record, "process_role", "unknown"),
            "category": getattr(record, "log_category", LOG_CATEGORY_APP),
            "module": record.module,
            "line": record.lineno,
            "process": record.process,
            "thread": record.threadName,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False)


def get_log_category() -> str:
    """获取当前调用链的日志分类。"""
    return _LOG_CATEGORY_VAR.get()


def set_log_category(category: str) -> contextvars.Token[str]:
    """设置当前调用链日志分类，返回 token 便于恢复。"""
    return _LOG_CATEGORY_VAR.set(category)


def reset_log_category(token: contextvars.Token[str]) -> None:
    """恢复之前的日志分类上下文。"""
    _LOG_CATEGORY_VAR.reset(token)


def build_log_file_paths(log_dir_root: str) -> LogFilePaths:
    """根据根目录生成实际日志文件路径。"""
    root_dir = Path(log_dir_root)
    if not root_dir.is_absolute():
        root_dir = (_PROJECT_ROOT / root_dir).resolve()

    app_dir = root_dir / "app"
    celery_dir = root_dir / "celery"
    app_dir.mkdir(parents=True, exist_ok=True)
    celery_dir.mkdir(parents=True, exist_ok=True)

    return LogFilePaths(
        root_dir=root_dir,
        app_log=app_dir / "app.log",
        task_log=celery_dir / "task.log",
        web_sync_log=celery_dir / "web_sync.log",
    )


def _build_formatter(log_format: str) -> logging.Formatter:
    """按配置构建 Formatter。"""
    if log_format == "json":
        return JsonFormatter()
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(process_role)s | %(log_category)s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _build_file_handler(
    *,
    path: Path,
    level: int,
    formatter: logging.Formatter,
    process_role: str,
    category: str,
    when: str,
    interval: int,
    backup_count: int,
) -> logging.Handler:
    """创建按天轮转的文件 Handler。"""
    handler = TimedRotatingFileHandler(
        filename=str(path),
        when=when,
        interval=interval,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    handler.addFilter(ContextEnricherFilter(process_role))
    handler.addFilter(CategoryFilter(category))
    return handler


def _normalize_logging_level(log_level: str) -> int:
    """将字符串日志级别转换为 logging 常量。"""
    return getattr(logging, str(log_level).upper(), logging.INFO)


def init_logging(process_role: Literal["app", "task"] = "app") -> LogFilePaths:
    """
    初始化全局日志。

    说明：
    - `process_role=app` 用于 FastAPI 进程；
    - `process_role=task` 用于 Celery worker / beat 进程。
    """
    import warnings

    # 过滤 jieba 库在 Python 3.12+ 产生的无效转义序列警告（SyntaxWarning）
    # jieba 0.42.1 是较老的库，正则表达式未使用 raw string
    warnings.filterwarnings(
        "ignore",
        category=SyntaxWarning,
        module="jieba.*"
    )
    warnings.filterwarnings(
        "ignore",
        message=r".*invalid escape sequence.*",
        category=SyntaxWarning
    )

    from core.config import settings

    file_paths = build_log_file_paths(settings.LOG_DIR_ROOT)
    log_level = _normalize_logging_level(settings.LOG_LEVEL)
    formatter = _build_formatter(settings.LOG_FORMAT)

    # 先清空 root handlers，避免热重载或重复导入时出现重复输出。
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    root_logger.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ContextEnricherFilter(process_role))

    root_logger.addHandler(console_handler)
    root_logger.addHandler(
        _build_file_handler(
            path=file_paths.app_log,
            level=log_level,
            formatter=formatter,
            process_role=process_role,
            category=LOG_CATEGORY_APP,
            when=settings.LOG_FILE_WHEN,
            interval=settings.LOG_FILE_INTERVAL,
            backup_count=settings.LOG_FILE_BACKUP_COUNT,
        )
    )
    root_logger.addHandler(
        _build_file_handler(
            path=file_paths.task_log,
            level=log_level,
            formatter=formatter,
            process_role=process_role,
            category=LOG_CATEGORY_TASK,
            when=settings.LOG_FILE_WHEN,
            interval=settings.LOG_FILE_INTERVAL,
            backup_count=settings.LOG_FILE_BACKUP_COUNT,
        )
    )
    root_logger.addHandler(
        _build_file_handler(
            path=file_paths.web_sync_log,
            level=log_level,
            formatter=formatter,
            process_role=process_role,
            category=LOG_CATEGORY_WEB_SYNC,
            when=settings.LOG_FILE_WHEN,
            interval=settings.LOG_FILE_INTERVAL,
            backup_count=settings.LOG_FILE_BACKUP_COUNT,
        )
    )

    # 让常见第三方 logger 统一走 root，避免各自加 handler 导致重复或分流失控。
    for logger_name in [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "celery",
        "celery.app.trace",
        "celery.worker",
        "kombu",
    ]:
        named_logger = logging.getLogger(logger_name)
        named_logger.handlers.clear()
        named_logger.propagate = True
        named_logger.setLevel(log_level)

    logging.captureWarnings(True)
    set_log_category(LOG_CATEGORY_TASK if process_role == "task" else LOG_CATEGORY_APP)
    logging.getLogger(__name__).info(
        "日志系统初始化完成，root=%s, app=%s, task=%s, web_sync=%s",
        file_paths.root_dir,
        file_paths.app_log,
        file_paths.task_log,
        file_paths.web_sync_log,
    )
    return file_paths
