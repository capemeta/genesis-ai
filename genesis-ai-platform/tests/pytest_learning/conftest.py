from __future__ import annotations

import shutil
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest

from tests.pytest_learning.helpers import UserProfile


@pytest.fixture
def sample_user() -> UserProfile:
    """提供一个可复用的测试用户。"""

    return UserProfile(username="alice", score=95, active=True)


@pytest.fixture
def sample_numbers() -> list[int]:
    """提供一个可复用的整数列表。"""

    return [1, 2, 3, 4]


@pytest.fixture
def workspace_tmp_path() -> Generator[Path, None, None]:
    """在项目目录下提供一个可清理的临时目录，便于当前环境稳定运行。"""

    base_dir = Path("tests") / "pytest_learning" / "_tmp_runtime"
    base_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = base_dir / uuid4().hex
    temp_dir.mkdir()

    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
