#!/bin/bash

# ============================================
# Genesis AI - 生产环境部署脚本
# ============================================

set -e  # 遇到错误立即退出

echo "=========================================="
echo "Genesis AI - 生产环境部署"
echo "=========================================="

# 安全检查：确认是否真的要部署到生产环境
echo ""
echo "⚠️  警告：您正在部署到生产环境！"
read -p "确认继续？(yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "❌ 部署已取消"
    exit 0
fi

# 检查 .env 文件是否存在
if [ ! -f .env ]; then
    echo ""
    echo "❌ 未发现 .env 文件"
    echo "📝 请先配置环境变量"
    exit 1
fi

# 检查是否修改了默认密码
if grep -q "9J#pLw!4sM\$nGfT6" .env; then
    echo ""
    echo "❌ 检测到默认密码！"
    echo "⚠️  生产环境必须修改默认密码"
    echo "📝 请编辑 .env 和 init-database.sql 文件"
    exit 1
fi

echo ""
echo "📦 启动生产环境容器..."
docker-compose up -d

echo ""
echo "⏳ 等待数据库就绪..."
sleep 15

# 检查容器状态
if docker ps | grep -q genesis-ai-db-prod; then
    echo ""
    echo "✅ 容器启动成功！"
    docker ps | grep genesis-ai-db-prod
    
    echo ""
    echo "📊 容器状态："
    docker-compose ps
    
    echo ""
    echo "🔒 安全检查："
    echo "   ✓ 容器运行正常"
    echo "   ✓ 密码已修改"
    
    echo ""
    echo "=========================================="
    echo "🎉 生产环境部署完成！"
    echo "=========================================="
    echo ""
    echo "📝 后续步骤："
    echo "1. 初始化数据库（首次运行）："
    echo "   仅当 ../pgdata-prod 为空时，容器首次启动会自动执行 init-database.sql"
    echo "   并自动导入 ../init-schema.sql 中的业务表结构和默认主数据"
    echo ""
    echo "2. 后续重启："
    echo "   已有数据时再次执行 docker-compose up -d 不会重复初始化数据库"
    echo ""
    echo "3. 强制重建（危险操作）："
    echo "   在 Linux / sh 环境下执行："
    echo "   sh ./reset-db.sh"
    echo ""
    echo "4. 连接数据库："
    echo "   docker exec -it genesis-ai-db-prod psql -U genesis_app -d genesis_ai"
    echo ""
    echo "5. 查看日志："
    echo "   docker-compose logs -f"
    echo ""
    echo "6. 备份数据库："
    echo "   docker exec genesis-ai-db-prod pg_dump -U genesis_app genesis_ai > backup.sql"
    echo ""
    echo "⚠️  重要提醒："
    echo "   - 定期备份数据库"
    echo "   - 监控容器资源使用"
    echo "   - 检查日志中的异常"
    echo ""
else
    echo ""
    echo "❌ 容器启动失败，请检查日志："
    echo "   docker-compose logs"
    exit 1
fi
