#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}启动 SeaweedFS 服务...${NC}"

# 检查 Docker 是否运行
docker info > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: Docker 未运行，请先启动 Docker${NC}"
    exit 1
fi

# 创建数据目录
if [ ! -d "data" ]; then
    mkdir -p data
    echo -e "${CYAN}创建目录: data${NC}"
fi

# 启动服务
echo -e "\n${GREEN}启动 Docker Compose 服务...${NC}"
docker compose up -d

# 等待服务启动
echo -e "\n${YELLOW}等待服务启动...${NC}"
sleep 5

# 检查服务状态
echo -e "\n${GREEN}服务状态:${NC}"
docker compose ps

# 显示访问信息
echo -e "\n${CYAN}==================================${NC}"
echo -e "${GREEN}SeaweedFS 服务已启动！${NC}"
echo -e "${CYAN}==================================${NC}"
echo -e ""
echo -e "${YELLOW}访问地址:${NC}"
echo -e "  Master UI:  http://localhost:8301"
echo -e "  Volume UI:  http://localhost:8302/ui/index.html"
echo -e "  Filer UI:   http://localhost:8303"
echo -e "  S3 API:     http://localhost:8304"
echo -e ""
echo -e "${YELLOW}查看日志:${NC}"
echo -e "  docker compose logs -f"
echo -e ""
echo -e "${YELLOW}停止服务:${NC}"
echo -e "  docker compose down"
echo -e "${CYAN}==================================${NC}"
