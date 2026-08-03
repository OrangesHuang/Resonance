from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from scheduler.tasks import start_scheduler, stop_scheduler
from api.signals import router as signals_router
from api.etf import router as etf_router
from api.realtime import router as realtime_router
from api.stats import router as stats_router
from api.sentiment import router as sentiment_router
from api.calendar import router as calendar_router
from api.resonance import router as resonance_router
from api.data import router as data_router
from api.portfolio import router as portfolio_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="ETF 国家队监控系统",
    description="三因子 ETF 国家队资金监测 — 盘中实时信号",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals_router)
app.include_router(etf_router)
app.include_router(realtime_router)
app.include_router(stats_router)
app.include_router(sentiment_router)
app.include_router(calendar_router)
app.include_router(resonance_router)
app.include_router(data_router)
app.include_router(portfolio_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
