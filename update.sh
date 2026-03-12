#!/bin/bash
# Karvis 一键更新脚本
set -e

echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] 开始更新 ==="

cd /opt/KarvisForYou

# 拉取最新代码
echo ">>> git pull..."
git pull origin main

# 重新构建镜像并重启（确保代码变更生效）
echo ">>> 重新构建并启动 karvis..."
docker compose -f deploy/docker-compose.yml up --build -d karvis

# 等待健康检查
echo ">>> 等待服务就绪..."
sleep 5
docker ps --filter name=karvis --format "table {{.Names}}\t{{.Status}}"

echo "=== 更新完成 ==="
