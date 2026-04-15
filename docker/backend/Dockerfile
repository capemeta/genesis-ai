ARG PYTHON_BASE_IMAGE=python:3.12-slim

# 此 Dockerfile 用于 backend 和大多数 worker（不包含 tesseract）
# tesseract 只在 parse-worker 中需要，已移至 Dockerfile.parse
FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

# 基础系统依赖（tesseract 相关包已移除）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir uv

WORKDIR /app/genesis-ai-platform

# 复制依赖文件并安装（使用 uv 优化 layer 缓存）
COPY genesis-ai-platform/pyproject.toml genesis-ai-platform/uv.lock ./
RUN uv sync --frozen --no-dev

# 复制应用代码
COPY genesis-ai-platform/ ./

EXPOSE 8200

# 默认命令，后续会被 docker-compose 的 command 覆盖
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8200"]
