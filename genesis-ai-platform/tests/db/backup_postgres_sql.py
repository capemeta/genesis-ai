"""
备份 PostgreSQL 数据库为可直接恢复的 plain SQL 文件。

使用方式（在 genesis-ai-platform 目录下执行）：
    uv run python tests/db/backup_postgres_sql.py

恢复方式示例：
    psql -h 127.0.0.1 -p 5432 -U postgres -d target_db -f tests/db/backups/genesis_ai_20260313_181500.sql
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence
from urllib.parse import quote_plus, unquote, urlsplit


CURRENT_FILE = Path(__file__).resolve()
PLATFORM_ROOT = CURRENT_FILE.parents[2]
DEFAULT_PG_DUMP_PATH = Path(r"E:\workspace\software\PostgreSQL\18\bin\pg_dump.exe")


@dataclass(slots=True)
class PostgresConnectionInfo:
    """封装 pg_dump 所需的 PostgreSQL 连接信息。"""

    host: str
    port: int
    username: str
    password: str | None
    database: str
    sslmode: str | None


def build_argument_parser() -> argparse.ArgumentParser:
    """构建命令行参数。"""
    parser = argparse.ArgumentParser(
        description="导出 PostgreSQL 全量 SQL 备份，可直接通过 psql 恢复到其他 PostgreSQL 数据库。"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="输出 SQL 文件路径。默认保存到 tests/db/backups/<数据库名>_<时间戳>.sql",
    )
    parser.add_argument(
        "--pg-dump-path",
        type=Path,
        help="pg_dump 可执行文件路径。未传时自动从 PATH 中查找。",
    )
    parser.add_argument(
        "--create-db",
        action="store_true",
        default=True,
        help="在导出文件中加入 CREATE DATABASE 语句，适合恢复到新的数据库环境。",
    )
    parser.add_argument(
        "--no-create-db",
        action="store_false",
        dest="create_db",
        help="不导出 CREATE DATABASE 语句，适合恢复到已存在的目标数据库。",
    )
    parser.add_argument(
        "--use-inserts",
        action="store_true",
        help="使用 INSERT 语句而不是 COPY 导出数据，兼容性更高但文件更大、速度更慢。",
    )
    parser.add_argument(
        "--exclude-table-data",
        action="append",
        default=[],
        metavar="TABLE",
        help="排除某张表的数据，可重复传入，例如 --exclude-table-data audit_logs",
    )
    return parser


def load_env_file(env_path: Path) -> dict[str, str]:
    """读取项目 .env 文件。"""
    if not env_path.exists():
        return {}

    env_map: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        env_map[key] = value

    return env_map


def resolve_database_url() -> str:
    """优先从 .env 的拆分配置中读取数据库连接，确保按 DB_NAME 导出目标库。"""
    env_map = load_env_file(PLATFORM_ROOT / ".env")
    merged_env = {**env_map, **os.environ}

    db_host = merged_env.get("DB_HOST")
    db_port = merged_env.get("DB_PORT", "5432")
    db_user = merged_env.get("DB_USER")
    db_password = merged_env.get("DB_PASSWORD")
    db_name = merged_env.get("DB_NAME")
    db_driver = merged_env.get("DB_DRIVER", "postgresql+asyncpg")

    if not all([db_host, db_user, db_password, db_name]):
        raise ValueError("未读取到完整数据库配置，请先检查 genesis-ai-platform/.env 或环境变量。")

    assert db_password is not None

    return (
        f"{db_driver}://{db_user}:{quote_plus(db_password)}@{db_host}:{db_port}/{db_name}"
    )


def parse_postgres_connection_info(database_url: str) -> PostgresConnectionInfo:
    """把 SQLAlchemy URL 转成 pg_dump 可直接使用的连接参数。"""
    parsed = urlsplit(database_url)
    scheme = parsed.scheme.lower()

    if not scheme.startswith("postgresql"):
        raise ValueError(f"当前数据库不是 PostgreSQL：{scheme}")
    if not parsed.hostname:
        raise ValueError("数据库配置缺少 host，无法执行 pg_dump。")
    if not parsed.username:
        raise ValueError("数据库配置缺少 username，无法执行 pg_dump。")
    database_name = parsed.path.lstrip("/")
    if not database_name:
        raise ValueError("数据库配置缺少 database name，无法执行 pg_dump。")

    sslmode = None
    if parsed.query:
        for pair in parsed.query.split("&"):
            if not pair or "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            if key == "sslmode":
                sslmode = value
                break

    return PostgresConnectionInfo(
        host=parsed.hostname,
        port=parsed.port or 5432,
        username=unquote(parsed.username),
        password=unquote(parsed.password) if parsed.password else None,
        database=database_name,
        sslmode=sslmode,
    )


def resolve_output_path(output_path: Path | None, database_name: str) -> Path:
    """解析输出文件路径，并确保目录存在。"""
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(r"D:\workspace\python\备份") / f"{database_name}_{timestamp}.sql"

    output_path = output_path if output_path.is_absolute() else PLATFORM_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def resolve_pg_dump_binary(custom_path: Path | None) -> str:
    """定位 pg_dump 可执行文件。"""
    if custom_path is not None:
        if not custom_path.exists():
            raise FileNotFoundError(f"指定的 pg_dump 不存在：{custom_path}")
        return str(custom_path)

    if DEFAULT_PG_DUMP_PATH.exists():
        return str(DEFAULT_PG_DUMP_PATH)

    binary = shutil.which("pg_dump")
    if binary:
        return binary

    raise FileNotFoundError(
        "未找到 pg_dump，请先安装 PostgreSQL 客户端，或通过 --pg-dump-path 指定 pg_dump.exe 路径。"
    )


def build_pg_dump_command(
    pg_dump_binary: str,
    conn: PostgresConnectionInfo,
    output_path: Path,
    create_db: bool,
    use_inserts: bool,
    exclude_table_data: Sequence[str],
) -> list[str]:
    """拼装 pg_dump 命令。"""
    command = [
        pg_dump_binary,
        f"--host={conn.host}",
        f"--port={conn.port}",
        f"--username={conn.username}",
        "--encoding=UTF8",
        "--format=plain",
        "--clean",
        "--if-exists",
        "--quote-all-identifiers",
        "--no-owner",
        "--no-privileges",
        f"--file={output_path}",
        conn.database,
    ]

    if create_db:
        command.insert(-2, "--create")

    if use_inserts:
        command.insert(-2, "--inserts")

    for table_name in exclude_table_data:
        command.insert(-2, f"--exclude-table-data={table_name}")

    return command


def build_pg_env(conn: PostgresConnectionInfo) -> dict[str, str]:
    """构建 pg_dump 运行环境，避免把密码直接暴露在命令参数里。"""
    env = os.environ.copy()
    if conn.password:
        env["PGPASSWORD"] = conn.password
    if conn.sslmode:
        env["PGSSLMODE"] = conn.sslmode
    return env


def print_restore_guide(output_path: Path, conn: PostgresConnectionInfo, create_db: bool) -> None:
    """输出恢复指引，方便后续直接执行。"""
    sql_path = output_path.as_posix()
    print("\n备份完成。")
    print(f"SQL 文件：{output_path}")
    print("\n恢复示例：")
    if create_db:
        print(f"  psql -h {conn.host} -p {conn.port} -U {conn.username} -d postgres -f {sql_path}")
    else:
        print(f"  psql -h {conn.host} -p {conn.port} -U {conn.username} -d <目标数据库> -f {sql_path}")


def main() -> int:
    """程序入口。"""
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        database_url = resolve_database_url()
        conn = parse_postgres_connection_info(database_url)
        output_path = resolve_output_path(args.output, conn.database)
        pg_dump_binary = resolve_pg_dump_binary(args.pg_dump_path)
        command = build_pg_dump_command(
            pg_dump_binary=pg_dump_binary,
            conn=conn,
            output_path=output_path,
            create_db=args.create_db,
            use_inserts=args.use_inserts,
            exclude_table_data=args.exclude_table_data,
        )
        env = build_pg_env(conn)

        print(f"开始备份数据库：{conn.database}")
        print(f"输出文件：{output_path}")
        print(f"使用工具：{pg_dump_binary}")

        subprocess.run(command, check=True, env=env)
        print_restore_guide(output_path, conn, args.create_db)
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"\npg_dump 执行失败，退出码：{exc.returncode}", file=sys.stderr)
        return exc.returncode
    except Exception as exc:
        print(f"\n备份失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
