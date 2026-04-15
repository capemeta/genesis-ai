# Backend Docker 构建说明

## 文件结构

- `Dockerfile` - 当前统一后端运行时镜像，供 backend / 全部 Celery worker / beat 复用

## 优化说明

**当前策略：**

1. 所有后端服务统一复用同一个运行时镜像
2. OCR 所需的 `tesseract-ocr` 与语言包直接安装进统一镜像
3. `docker-compose.full.yml` 中只有 `backend` 带 `build`
4. 其余 worker / beat 仅复用同一个 `image`，避免首次冷构建时重复执行 `uv sync`

## 构建命令

```powershell
# 首次部署或依赖变更时，先只构建统一后端镜像
docker compose --env-file .\docker\.env -f .\docker\docker-compose.full.yml build backend

# 再启动全部服务
docker compose --env-file .\docker\.env -f .\docker\docker-compose.full.yml up -d
```

## 说明

- `parse-worker`、`chunk-worker`、`enhance-worker`、`train-worker`、`websync-worker`、`default-worker`、`celery-beat` 均直接复用 `backend` 构建出的镜像
- 首次冷构建时，Python 依赖只需要完整下载一次
- 如果你看到 OCR 相关错误，请优先检查统一后端镜像中的 `tesseract` 是否安装成功
