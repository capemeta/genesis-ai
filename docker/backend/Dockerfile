ARG PYTHON_BASE_IMAGE=python:3.12-slim

# 统一后端运行时镜像：
# - backend / 全部 Celery worker / beat 共用这一份镜像
# - OCR 依赖一并安装，避免首次冷构建时因为多镜像并发执行 uv sync 而重复下载大体积 Python 依赖
FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

# 统一安装运行时系统依赖（包含 OCR 所需的 tesseract 及语言包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir uv

WORKDIR /app/genesis-ai-platform

# 复制依赖文件并安装（使用 uv 优化 layer 缓存）
COPY genesis-ai-platform/pyproject.toml genesis-ai-platform/uv.lock genesis-ai-platform/uv.toml ./
RUN uv sync --frozen --no-dev

# 复制应用代码
COPY genesis-ai-platform/ ./

EXPOSE 8200

# 默认命令，后续会被 docker-compose 的 command 覆盖
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8200"]
