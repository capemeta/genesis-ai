# Backend Docker 构建说明

## 文件结构

- `Dockerfile.base` - 基础镜像（不包含 tesseract-ocr），用于 backend 和大多数 Celery worker
- `Dockerfile` - 实际用于 backend 和非 parse worker（FROM Dockerfile.base 的简化版）
- `Dockerfile.parse` - 专用于 parse-worker，包含 tesseract-ocr 及其语言包（eng + chi_sim）

## 优化说明

**之前的问题：**
- 所有 8 个后端服务（backend + 7 个 worker）都安装 tesseract-ocr + 中文/英文语言包
- 导致每个镜像都 ~1.95GB，且重复打包不必要的依赖
- 不同 worker 构建出不同的 Image ID，未有效共享 Docker layer

**现在的优化：**

1. **parse-worker** 专用镜像：仅此容器包含 tesseract（OCR 解析必需）
2. **其他服务** 使用轻量基础镜像：减少 ~80-150MB/镜像
3. **docker-compose.full.yml** 使用 YAML anchor 分别指定构建配置
4. 共享 Python 依赖层（`uv sync`），构建缓存更高效

## 构建命令

```powershell
# 重新构建所有服务（会使用新的优化配置）
docker compose --env-file .\docker\.env -f .\docker\docker-compose.full.yml up -d --build

# 只重建 parse-worker（包含 tesseract）
docker compose --env-file .\docker\.env -f .\docker\docker-compose.full.yml build parse-worker

# 只重建其他后端服务（轻量版）
docker compose --env-file .\docker\.env -f .\docker\docker-compose.full.yml build backend chunk-worker
```

## 镜像体积对比（预期）

- `parse-worker`: ~1.95GB（包含 tesseract）
- `backend` / `chunk-worker` / `enhance-worker` 等: 减少 80-150MB
- 总体磁盘占用显著降低，首次拉取速度提升

## 注意事项

- `pytesseract` Python 包仍在所有服务中安装（因为是共享依赖）
- 但 **系统层** 的 tesseract 可执行文件和语言数据只在 parse-worker 中存在
- 如果你看到 parse-worker 启动报 tesseract 相关错误，请检查语言包是否正确安装
