@echo off
REM SeaweedFS 启动脚本 (CMD)

echo 启动 SeaweedFS 服务...

REM 检查 Docker 是否运行
docker info >nul 2>&1
if errorlevel 1 (
    echo 错误: Docker 未运行，请先启动 Docker Desktop
    exit /b 1
)

REM 创建数据目录
if not exist "data" mkdir "data"

REM 启动服务
echo.
echo 启动 Docker Compose 服务...
docker-compose up -d

REM 等待服务启动
echo.
echo 等待服务启动...
timeout /t 5 /nobreak >nul

REM 检查服务状态
echo.
echo 服务状态:
docker-compose ps

REM 显示访问信息
echo.
echo ==================================
echo SeaweedFS 服务已启动！
echo ==================================
echo.
echo 访问地址:
echo   Master UI:  http://localhost:8301
echo   Volume UI:  http://localhost:8302/ui/index.html
echo   Filer UI:   http://localhost:8303
echo   S3 API:     http://localhost:8304
echo.
echo 查看日志:
echo   docker-compose logs -f
echo.
echo 停止服务:
echo   docker-compose down
echo ==================================

pause
