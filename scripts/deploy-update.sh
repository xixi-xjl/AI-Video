#!/bin/bash
# 服务器上一键更新：git pull + 构建前端 + 重启后端
# 用法：bash /www/wwwroot/AI-Video/scripts/deploy-update.sh

set -e
cd /www/wwwroot/AI-Video

echo "===== 1. 拉取代码 ====="
git pull || git pull https://ghproxy.net/https://github.com/xixi-xjl/AI-Video.git main

echo "===== 2. 构建前端 ====="
export PATH=/www/server/nodejs/v20.13.1/bin:$PATH
cd frontend
npm install
npm run build

echo "===== 3. 重启后端 ====="
pkill -9 -f uvicorn 2>/dev/null || true
sleep 2
cd ../backend
nohup .venv/bin/python -u -m uvicorn main:app --host 127.0.0.1 --port 8000 > /tmp/ai.log 2>&1 &
sleep 10

echo "===== 4. 健康检查 ====="
curl -s http://127.0.0.1:8000/api/health
echo ""
echo "===== 更新完成 ====="
