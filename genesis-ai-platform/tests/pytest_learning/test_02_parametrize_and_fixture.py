from __future__ import annotations

import pytest

from tests.pytest_learning.helpers import UserProfile


def is_even(value: int) -> bool:
    """演示参数化测试。"""

    return value % 2 == 0


def build_display_name(user: UserProfile) -> str:
    """演示 fixture 返回对象如何参与业务逻辑测试。"""

    status = "active" if user.active else "inactive"
    return f"{user.username}:{status}:{user.score}"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (2, True),
        (3, False),
        (10, True),
    ],
)
def test_is_even(value: int, expected: bool) -> None:
    """一组逻辑，多组输入输出时适合使用参数化。"""

    assert is_even(value) is expected


def test_fixture_can_supply_object(sample_user: UserProfile) -> None:
    """fixture 会按参数名自动注入到测试函数中。"""

    assert build_display_name(sample_user) == "alice:active:95"


def test_fixture_can_supply_simple_list(sample_numbers: list[int]) -> None:
    """fixture 也很适合抽离重复的测试数据。"""

    assert sum(sample_numbers) == 10
