from __future__ import annotations

import asyncio


async def async_add(a: int, b: int) -> int:
    """演示异步函数测试。"""

    await asyncio.sleep(0)
    return a + b


async def fetch_status() -> dict[str, str]:
    """演示异步返回结构断言。"""

    await asyncio.sleep(0)
    return {"status": "ok", "source": "pytest"}


async def test_async_add() -> None:
    """项目已配置 pytest-asyncio，可直接编写 async 测试。"""

    assert await async_add(4, 5) == 9


async def test_async_dict_result() -> None:
    """异步测试中依然直接使用 assert 即可。"""

    result = await fetch_status()
    assert result["status"] == "ok"
    assert result["source"] == "pytest"
