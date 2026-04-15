from __future__ import annotations

import pytest


def add(a: int, b: int) -> int:
    """演示最基础的纯函数测试。"""

    return a + b


def divide(a: float, b: float) -> float:
    """演示异常测试。"""

    if b == 0:
        raise ValueError("除数不能为 0")
    return a / b


def join_name(first_name: str, last_name: str) -> str:
    """演示字符串结果断言。"""

    return f"{first_name} {last_name}"


def test_add_returns_expected_sum() -> None:
    """最常见的 pytest 用法就是直接 assert 结果。"""

    assert add(2, 3) == 5


def test_string_join() -> None:
    """字符串断言和普通布尔表达式写法完全一致。"""

    full_name = join_name("Ada", "Lovelace")
    assert full_name == "Ada Lovelace"
    assert "Ada" in full_name


def test_divide_raises_error_when_zero() -> None:
    """使用 pytest.raises 断言代码会抛出指定异常。"""

    with pytest.raises(ValueError, match="除数不能为 0"):
        divide(10, 0)
