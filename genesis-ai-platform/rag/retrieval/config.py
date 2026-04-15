"""
检索后端配置解析
"""
from dataclasses import dataclass

from core.config import settings


@dataclass(slots=True)
class ActiveSearchBackends:
    """当前启用的检索后端配置。"""

    vector_backend: str
    lexical_backend: str


def get_active_search_backends() -> ActiveSearchBackends:
    """读取当前激活的检索后端。

    当前阶段仅从 `.env` 读取全局默认值。
    未来如果启用知识库级覆盖，可在这里扩展解析顺序。
    """
    return ActiveSearchBackends(
        vector_backend=settings.DEFAULT_VECTOR_SEARCH_BACKEND,
        lexical_backend=settings.DEFAULT_LEXICAL_SEARCH_BACKEND,
    )
