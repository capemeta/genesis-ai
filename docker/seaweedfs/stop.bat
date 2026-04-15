@echo off
REM SeaweedFS 停止脚本 (CMD)

echo 停止 SeaweedFS 服务...

docker-compose down

echo.
echo SeaweedFS 服务已停止

pause
