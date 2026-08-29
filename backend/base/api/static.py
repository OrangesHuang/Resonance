"""生产模式静态托管: 前端 dist 产物由后端单进程服务。

适用场景: 单机/局域网个人部署(无需 nginx)。前端构建产物存在时挂载:
  - /assets/*        → 构建哈希文件名, 长缓存(协商缓存 + 不可变标记)
  - /<任意路径>       → SPA history 路由回退到 index.html(/api 前缀除外)
若 frontend/dist 不存在(纯 API 模式)则不做任何事, 不影响现有接口。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

# backend/base/api/static.py → 仓库根/frontend/dist
FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
INDEX_HTML = FRONTEND_DIST / "index.html"
_ASSETS_PREFIX = "/assets"
_ASSETS_TTL = "public, max-age=31536000, immutable"  # 哈希文件名可永久缓存


def mount_frontend(app: FastAPI) -> bool:
    """挂载前端静态产物, 返回是否挂载成功。须在所有 API 路由注册后调用。"""
    if not (INDEX_HTML.is_file() and (FRONTEND_DIST / "assets").is_dir()):
        return False

    assets_dir = FRONTEND_DIST / "assets"

    # 哈希文件名资源: 永久缓存(immutable)。本版本 StaticFiles 不支持
    # headers 参数, 用自定义路由 + FileResponse 加缓存头; 曾漏加缓存头
    # 导致浏览器启发式缓存 index.html, 部署后旧页面不失效(2026-08 修复)。
    @app.get(f"{_ASSETS_PREFIX}/{{path:path}}", include_in_schema=False)
    def assets_file(path: str):
        target = (assets_dir / path).resolve()
        if not target.is_file() or not target.is_relative_to(assets_dir.resolve()):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return FileResponse(target, headers={"Cache-Control": _ASSETS_TTL})

    # SPA 入口: no-cache → 每次请求重新协商(ETag/Last-Modified),
    # 部署后新 index.html 自动生效, 无需用户强刷
    _INDEX_HEADERS = {"Cache-Control": "no-cache"}

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(request: Request, full_path: str):
        # /api 前缀交给既有路由(未匹配时返回标准 404 JSON)
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if full_path:
            target = FRONTEND_DIST / full_path
            # 防目录穿越: 只服务 dist 内的真实文件
            if target.is_file() and target.resolve().is_relative_to(FRONTEND_DIST.resolve()):
                return FileResponse(target, headers=_INDEX_HEADERS)
        return FileResponse(INDEX_HTML, headers=_INDEX_HEADERS)

    return True
