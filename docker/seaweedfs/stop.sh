#!/bin/bash

# 颜色定义
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${YELLOW}停止 SeaweedFS 服务...${NC}"

docker compose down

echo -e "\n${GREEN}SeaweedFS 服务已停止${NC}"
