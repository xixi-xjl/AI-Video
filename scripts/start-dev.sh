#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "[错误] 未找到虚拟环境: ${ROOT}/.venv"
  echo "请先执行: python3 -m venv ${ROOT}/.venv && ${ROOT}/.venv/bin/pip install -r ${ROOT}/backend/requirements.txt"
  exit 1
fi

if [ ! -f "${ROOT}/.env" ]; then
  echo "[警告] 未找到配置文件: ${ROOT}/.env"
  echo "请执行: cp ${ROOT}/.env.example ${ROOT}/.env 并填入 API Key"
  exit 1
fi

echo "启动后端 http://localhost:8000 ..."
(cd "${ROOT}/backend" && "$PYTHON" main.py) &
BACKEND_PID=$!

sleep 2

echo "启动前端 http://localhost:5173 ..."
(cd "${ROOT}/frontend" && npm run dev) &
FRONTEND_PID=$!

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null' EXIT

echo ""
echo "用户端:   http://localhost:5173"
echo "管理后台: http://localhost:5173/admin"
echo "API 文档: http://localhost:8000/docs"
echo "按 Ctrl+C 停止"
wait
