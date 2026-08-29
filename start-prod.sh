#!/usr/bin/env bash
# 生产模式启动脚本: 前端构建为 dist 制品, 由后端单进程托管并暴露。
# 单进程部署(无需 nginx) — 适合单机/局域网个人使用。
#
# 用法:
#   ./start-prod.sh              # 前台运行 (http://<本机IP>:8001)
#   ./start-prod.sh --daemon     # 后台运行, 日志 prod.out
#   PORT=8080 ./start-prod.sh    # 自定义端口
#   ./start-prod.sh --skip-build # 跳过前端构建(已构建过)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV_DIR="$ROOT/.venv"
PORT="${PORT:-8001}"
SKIP_BUILD=false
DAEMON=false
for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=true ;;
    --daemon) DAEMON=true ;;
    *) echo "未知参数: $arg (支持 --skip-build / --daemon)" >&2; exit 1 ;;
  esac
done

log() { printf '\033[0;36m[start-prod]\033[0m %s\n' "$*"; }
die() { printf '\033[0;31m[start-prod]\033[0m %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "未找到 python3, 请先安装 Python 3.9+。"
command -v npm >/dev/null 2>&1 || die "未找到 npm, 请先安装 Node.js。"

# --- 依赖准备(与 start.sh 相同策略: 已装齐则跳过) ---
deps_satisfied() {
  [ -f "$VENV_DIR/.requirements.snapshot" ] \
    && cmp -s "$VENV_DIR/.requirements.snapshot" "$BACKEND_DIR/requirements.txt" \
    && "$VENV_DIR/bin/python" -c 'import fastapi, uvicorn, apscheduler' >/dev/null 2>&1
}
if ! "$VENV_DIR/bin/pip" --version >/dev/null 2>&1; then
  log "创建虚拟环境 .venv ..."
  rm -rf "$VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi
if ! deps_satisfied; then
  log "安装后端依赖 ..."
  "$VENV_DIR/bin/pip" install --quiet -r "$BACKEND_DIR/requirements.txt" || die "依赖安装失败"
  cp "$BACKEND_DIR/requirements.txt" "$VENV_DIR/.requirements.snapshot"
fi
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  log "安装前端依赖 ..."
  (cd "$FRONTEND_DIR" && npm install --silent)
fi

# --- 前端构建为制品 ---
if [ "$SKIP_BUILD" = false ]; then
  log "构建前端 → frontend/dist ..."
  (cd "$FRONTEND_DIR" && npm run build) || die "前端构建失败"
fi
[ -f "$FRONTEND_DIR/dist/index.html" ] || die "frontend/dist 不存在, 请先构建(去掉 --skip-build)"

# --- 释放端口 + 启动 ---
lsof -ti ":$PORT" | xargs kill -9 2>/dev/null || true
sleep 1

UVICORN_CMD=(
  "$VENV_DIR/bin/python" -m uvicorn main:app
  --host "${HOST:-0.0.0.0}" --port "$PORT"
)

if [ "$DAEMON" = true ]; then
  log "后台启动 → http://0.0.0.0:$PORT (日志: $ROOT/prod.out)"
  (cd "$BACKEND_DIR" && exec "${UVICORN_CMD[@]}") > "$ROOT/prod.out" 2>&1 &
  echo "$!" > "$ROOT/prod.pid"
  log "PID: $(cat $ROOT/prod.pid)  停止: kill $(cat $ROOT/prod.pid)"
  exit 0
fi

log "启动生产服务 http://0.0.0.0:$PORT (Ctrl+C 停止)"
cd "$BACKEND_DIR"
exec "${UVICORN_CMD[@]}"