#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
POSTGRESQL_DIR=$(dirname -- "$SCRIPT_DIR")
DATA_DIR="$POSTGRESQL_DIR/pgdata-prod"
CONTAINER_NAME="genesis-ai-db-prod"
DATABASE_NAME="genesis_ai"
CONFIRMATION_TEXT="RESET $DATABASE_NAME"

compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    docker compose "$@"
  fi
}

wait_for_container_healthy() {
  name="$1"
  timeout_seconds="${2:-180}"
  elapsed=0

  while [ "$elapsed" -lt "$timeout_seconds" ]; do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$name" 2>/dev/null || true)"
    if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
      return 0
    fi

    sleep 2
    elapsed=$((elapsed + 2))
  done

  return 1
}

cd "$SCRIPT_DIR"

echo "=========================================="
echo "Genesis AI - 生产环境强制重建数据库"
echo "=========================================="
echo
echo "将删除的数据目录：$DATA_DIR"
echo "目标容器：$CONTAINER_NAME"
echo "目标数据库：$DATABASE_NAME"
echo
echo "警告：该操作会永久删除生产环境 PostgreSQL 数据。"
printf "请输入 %s 继续： " "$CONFIRMATION_TEXT"
read -r confirmation

if [ "$confirmation" != "$CONFIRMATION_TEXT" ]; then
  echo "确认串不匹配，已取消强制重建。"
  exit 1
fi

# 先停容器，再删除数据目录，避免 PostgreSQL 仍占用数据文件。
echo
echo "1. 停止生产环境容器..."
compose down --remove-orphans

if [ -d "$DATA_DIR" ]; then
  echo
  echo "2. 删除旧数据目录..."
  rm -rf "$DATA_DIR"
else
  echo
  echo "2. 数据目录不存在，跳过删除。"
fi

echo
echo "3. 重新启动生产环境容器..."
compose up -d

echo
echo "4. 等待 PostgreSQL 就绪..."
if ! wait_for_container_healthy "$CONTAINER_NAME" 180; then
  echo "等待容器 $CONTAINER_NAME 就绪超时。"
  exit 1
fi

echo
echo "生产环境数据库已强制重建完成（已自动导入 init-schema.sql）。"
