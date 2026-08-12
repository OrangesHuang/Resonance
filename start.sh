#!/usr/bin/env bash
# 一键启动脚本：从 fresh clone 直接拉起前后端。
# 自动创建虚拟环境、安装依赖（仅缺失时），然后同时启动后端(:8001)与前端(:5174)。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# 自动后台化: 如果在交互终端且未指定 --foreground, 则用 nohup 后台启动
if [[ -t 0 && "${1:-}" != "--foreground" ]]; then
  echo "[start] 检测到交互终端, 自动后台启动 (nohup)"
  echo "[start] 日志: $ROOT/nohup.out"
  echo "[start] 停止: pkill -f 'uvicorn main:app.*--port 8001'"
  nohup "$0" --foreground > "$ROOT/nohup.out" 2>&1 &
  echo "[start] 已后台启动, PID: $!"
  exit 0
fi

BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV_DIR="$ROOT/.venv"
BACKEND_PORT=8001
FRONTEND_PORT=5174

log() { printf '\033[0;36m[start]\033[0m %s\n' "$*"; }
die() { printf '\033[0;31m[start]\033[0m %s\n' "$*" >&2; exit 1; }

# 镜像自动探测: 依次试 阿里云 → 清华 → pypi, 取首个可达者(3s 连接超时)
PIP_MIRRORS=(
  "https://mirrors.aliyun.com/pypi/simple/"
  "https://pypi.tuna.tsinghua.edu.cn/simple/"
  "https://pypi.org/simple/"
)
pick_pip_mirror() {
  for m in "${PIP_MIRRORS[@]}"; do
    if curl -sS -o /dev/null --connect-timeout 3 --max-time 6 "$m/pip/" 2>/dev/null; then
      echo "$m"
      return 0
    fi
    log "镜像不可达: $m" >&2
  done
  return 1
}

command -v python3 >/dev/null 2>&1 || die "未找到 python3，请先安装 Python 3.9+。"
command -v npm     >/dev/null 2>&1 || die "未找到 npm，请先安装 Node.js。"

# 依赖已装齐(requirements 未变 + 关键包可导入)则完全跳过 pip, 保证坏网络下也能秒级启动
deps_satisfied() {
  [ -f "$VENV_DIR/.requirements.snapshot" ] \
    && cmp -s "$VENV_DIR/.requirements.snapshot" "$BACKEND_DIR/requirements.txt" \
    && "$VENV_DIR/bin/python" -c 'import fastapi, uvicorn, apscheduler' >/dev/null 2>&1
}

# --- 0. 杀掉旧进程 + 清理缓存（确保每次启动都用最新代码）---
log "释放端口 $BACKEND_PORT $FRONTEND_PORT ..."
lsof -ti ":$BACKEND_PORT" | xargs kill -9 2>/dev/null || true
lsof -ti ":$FRONTEND_PORT" | xargs kill -9 2>/dev/null || true
find "$BACKEND_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BACKEND_DIR" -name "*.pyc" -delete 2>/dev/null || true
sleep 1

# --- 1. Python 虚拟环境 + 后端依赖 ---
if ! "$VENV_DIR/bin/pip" --version >/dev/null 2>&1; then
  log "(重新)创建虚拟环境 .venv ..."
  rm -rf "$VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi
if ! deps_satisfied; then
  log "安装/校验后端依赖 ..."
  # 镜像探测仅在真正需要安装时执行, 减少坏网络下的启动等待
  if [ -z "${PIP_INDEX_URL:-}" ]; then
    MIRROR="$(pick_pip_mirror || true)"
    if [ -n "$MIRROR" ]; then
      export PIP_INDEX_URL="$MIRROR"
      log "使用镜像: $MIRROR"
    fi
  fi
  "$VENV_DIR/bin/pip" install --quiet --timeout 15 --retries 2 --upgrade pip 2>/dev/null || log "pip 升级跳过(网络不可用, 不影响)"
  "$VENV_DIR/bin/pip" install --quiet --timeout 30 --retries 2 -r "$BACKEND_DIR/requirements.txt" || die "依赖安装失败, 请检查网络后重试"
  cp "$BACKEND_DIR/requirements.txt" "$VENV_DIR/.requirements.snapshot"
fi

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

log "启动后端 http://localhost:$BACKEND_PORT （--reload 自动重载代码修改）"
(cd "$BACKEND_DIR" && exec "$VENV_DIR/bin/python" -m uvicorn main:app --port "$BACKEND_PORT" --reload) &
PIDS+=($!)

log "启动前端 http://localhost:$FRONTEND_PORT"
(cd "$FRONTEND_DIR" && exec npm run dev -- --host 0.0.0.0) &
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
