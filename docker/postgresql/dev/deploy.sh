#!/bin/bash

# ============================================
# Genesis AI - 开发环境部署脚本
# ============================================

set -e  # 遇到错误立即退出

echo "=========================================="
echo "Genesis AI - 开发环境部署"
echo "=========================================="

# 检查 .env 文件是否存在
if [ ! -f .env ]; then
    echo "❌ 未发现 .env 文件"
    echo "📝 请先配置环境变量"
    exit 1
fi

echo ""
echo "📦 启动开发环境容器..."
docker-compose up -d

echo ""
echo "⏳ 等待数据库就绪..."
sleep 10

# 检查容器状态
if docker ps | grep -q genesis-ai-db-dev; then
    echo ""
    echo "✅ 容器启动成功！"
    docker ps | grep genesis-ai-db-dev
    
    echo ""
    echo "📊 容器状态："
    docker-compose ps
    
    echo ""
    echo "=========================================="
    echo "🎉 开发环境部署完成！"
    echo "=========================================="
    echo ""
    echo "📝 后续步骤："
    echo "1. 初始化数据库（首次运行）："
    echo "   仅当 ../pgdata-dev 为空时，容器首次启动会自动执行 init-database.sh"
    echo "   并自动导入 ../init-schema.sql 中的业务表结构和默认主数据"
    echo ""
    echo "2. 后续重启："
    echo "   已有数据时再次执行 docker-compose up -d 不会重复初始化数据库"
    echo ""
    echo "3. 强制重建（危险操作）："
    echo "   在 Windows / PowerShell 下执行："
    echo "   .\\reset-db.ps1"
    echo ""
    echo "4. 连接数据库："
    echo "   docker exec -it genesis-ai-db-dev psql -U genesis_app -d genesis_ai"
    echo ""
    echo "5. 查看日志："
    echo "   docker-compose logs -f"
    echo ""
else
    echo ""
    echo "❌ 容器启动失败，请检查日志："
    echo "   docker-compose logs"
    exit 1
fi
