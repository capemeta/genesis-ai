"""
诊断 PostgreSQL 连接数：查看 max_connections、当前连接数、以及谁在占用连接。
在出现 TooManyConnectionsError 时，可用本脚本排查（若已满，需用超级用户连接）。

用法（在 genesis-ai-platform 目录下）：
  uv run python scripts/check_db_connections.py

若当前普通用户已无法连接，可用超级用户连接后执行脚本内打印的 SQL（见下方）。
"""
import asyncio
import sys
import os

# 确保能导入 core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings


def get_asyncpg_url() -> str:
    """把 SQLAlchemy 的 postgresql+asyncpg:// 转成 asyncpg 可用的 postgresql://"""
    url = settings.get_database_url()
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        return url
    return url


async def main():
    try:
        import asyncpg
    except ImportError:
        print("请安装 asyncpg: uv add asyncpg")
        return

    url = get_asyncpg_url()
    print("连接数据库（使用当前 .env 中的配置）...")
    try:
        conn = await asyncpg.connect(url)
    except Exception as e:
        print(f"连接失败: {e}")
        print("\n若因连接数已满无法连接，请用【超级用户】在 psql 或客户端中执行下面 SQL 查看占用：")
        print("-- 查看上限与当前数")
        print("SELECT (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_connections,")
        print("       (SELECT count(*) FROM pg_stat_activity) AS current_connections;")
        print("-- 按应用名、状态统计")
        print("SELECT application_name, state, count(*) FROM pg_stat_activity GROUP BY 1, 2 ORDER BY 3 DESC;")
        print("-- 终止某用户的所有空闲连接（慎用，把 your_user 换成实际用户名）")
        print("-- SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND usename = 'your_user';")
        return

    try:
        max_conn = await conn.fetchval("SELECT setting::int FROM pg_settings WHERE name = 'max_connections'")
        cur_conn = await conn.fetchval("SELECT count(*) FROM pg_stat_activity")
        rows = await conn.fetch("""
            SELECT application_name, state, usename, count(*) AS cnt
            FROM pg_stat_activity
            GROUP BY application_name, state, usename
            ORDER BY cnt DESC
        """)
        print(f"\n=== PostgreSQL 连接诊断 ===")
        print(f"max_connections (上限): {max_conn}")
        print(f"当前连接数:           {cur_conn}")
        print(f"剩余槽位:             {max_conn - cur_conn} (其中部分可能仅限 superuser)")
        print(f"\n按 application_name / state / 用户 统计:")
        for r in rows:
            app = r["application_name"] or "(null)"
            state = r["state"] or "(null)"
            user = r["usename"] or "(null)"
            print(f"  {app!r} | state={state!r} | user={user!r} => {r['cnt']} 个连接")
    finally:
        await conn.close()
    print("\n完成。")


if __name__ == "__main__":
    asyncio.run(main())
