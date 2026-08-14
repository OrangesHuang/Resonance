"""App 组装入口: 路由注册 + CORS + 前端静态托管(生产)。仅组装, 无业务逻辑。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.calendar import router as calendar_router
from api.data import router as data_router
from api.realtime import router as realtime_router
from api.signals import router as signals_router
from api.stats import router as stats_router
from base.api.etf import router as etf_router
from base.api.sentiment import router as sentiment_router
from base.api.static import mount_frontend
from base.scheduler.tasks import start_scheduler, stop_scheduler
from portfolio.api import router as portfolio_router
from resonance.api import router as resonance_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="ETF 买卖分析系统", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in (
    signals_router,
    etf_router,
    realtime_router,
    stats_router,
    sentiment_router,
    calendar_router,
    resonance_router,
    data_router,
    portfolio_router,
):
    app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


mount_frontend(app)
