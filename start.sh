#!/usr/bin/env bash
# 一键启动脚本：从 fresh clone 直接拉起前后端。
# 自动创建虚拟环境、安装依赖（仅缺失时），然后同时启动后端(:8000)与前端(:5173)。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV_DIR="$ROOT/.venv"
BACKEND_PORT=8000
FRONTEND_PORT=5173

log() { printf '\033[0;36m[start]\033[0m %s\n' "$*"; }
die() { printf '\033[0;31m[start]\033[0m %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "未找到 python3，请先安装 Python 3.9+。"
command -v npm     >/dev/null 2>&1 || die "未找到 npm，请先安装 Node.js。"

# --- 1. Python 虚拟环境 + 后端依赖 ---
if [ ! -d "$VENV_DIR" ]; then
  log "创建虚拟环境 .venv ..."
  python3 -m venv "$VENV_DIR"
fi
log "安装/校验后端依赖 ..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$BACKEND_DIR/requirements.txt"

# --- 2. 前端依赖 ---
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  log "安装前端依赖 (npm install) ..."
  (cd "$FRONTEND_DIR" && npm install --silent)
fi

# --- 3. 启动前后端，退出时统一清理 ---
PIDS=()
cleanup() {
  log "停止服务 ..."
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

log "启动后端 http://localhost:$BACKEND_PORT （首次启动会自动回填情绪数据并预加载K线，约 1-2 分钟）"
(cd "$BACKEND_DIR" && exec "$VENV_DIR/bin/python" -m uvicorn main:app --port "$BACKEND_PORT") &
PIDS+=($!)

log "启动前端 http://localhost:$FRONTEND_PORT"
(cd "$FRONTEND_DIR" && exec npm run dev) &
PIDS+=($!)

cat <<EOF

  前端:  http://localhost:$FRONTEND_PORT
  后端:  http://localhost:$BACKEND_PORT
  健康:  http://localhost:$BACKEND_PORT/api/health

  提示: 全新克隆的数据库为空。首次启动会自动回填市场情绪，
        但 ETF 日度历史需手动重建 —— 打开前端「数据管理」页点「一键重建」即可。
  按 Ctrl+C 停止全部服务。
EOF

wait
