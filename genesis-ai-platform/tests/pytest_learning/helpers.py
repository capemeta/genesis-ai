from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UserProfile:
    """用于演示 fixture 返回对象的简单数据结构。"""

    username: str
    score: int
    active: bool
