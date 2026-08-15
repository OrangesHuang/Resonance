"""任务注册表:任务名 → 元信息(label/exclusive/defaults) 与执行函数映射。"""

from __future__ import annotations

from collections.abc import Callable

from base.config import (
    DEFAULT_CHUNK_DAYS,
    DEFAULT_ETF_SEED_DAYS,
    DEFAULT_SHARES_BACKFILL_DAYS,
    SENTIMENT_BACKFILL_DAYS,
)
from base.scheduler.data_jobs import job_sync_calendar
from base.scheduler.etf_daily_jobs import job_backfill_etf_daily
from base.scheduler.rebuild import job_rebuild_all
from base.scheduler.recalc import job_recalc_composite
from base.scheduler.sentiment_jobs import job_fetch_etf_latest, job_fetch_sentiment
from base.scheduler.shares_jobs import job_backfill_missing_shares, job_backfill_shares

JOB_DEFS: dict[str, dict] = {
    "sync_calendar": {
        "label": "同步交易日历",
        "exclusive": False,
        "defaults": {},
        "data_flow": [
            {"step": "fetch", "text": "远端 A 股交易日历（历史 + 未来休市安排）"},
            {"step": "write", "text": "写入 calendar 表，供回填/定时任务判定交易日"},
        ],
    },
    "backfill_etf_daily": {
        "label": "回填ETF日度数据",
        "exclusive": False,
        "defaults": {
            "days": DEFAULT_ETF_SEED_DAYS,
            "force": False,
            "start_date": None,
            "end_date": None,
            "chunk_days": DEFAULT_CHUNK_DAYS,
        },
        "data_flow": [
            {"step": "fetch", "text": "拉取监控 ETF 与基准指数日 K 线（前复权 OHLCV）"},
            {"step": "derive", "text": "量能链 volume_ma20 → volume_ratio → vol_prob"},
            {
                "step": "derive",
                "text": "方向链 change_pct/5日涨幅 → dir_prob；价格位置 price_position + trade_direction（60日分位）",
            },
            {"step": "derive", "text": "综合概率 composite_prob → signal_level（V2 四层门控）"},
            {"step": "write", "text": "upsert 写入 etf_daily，已存在的日期跳过（勾选强制则覆盖）"},
        ],
    },
    "backfill_shares": {
        "label": "回填份额数据",
        "exclusive": False,
        "defaults": {
            "days": DEFAULT_SHARES_BACKFILL_DAYS,
            "force": False,
            "start_date": None,
            "end_date": None,
            "chunk_days": DEFAULT_CHUNK_DAYS,
        },
        "data_flow": [
            {"step": "fetch", "text": "拉取上交所（官方接口）+ 深交所（akshare）ETF 份额"},
            {"step": "derive", "text": "与前一交易日差分 → delta_yi / delta_pct → share_prob"},
            {"step": "write", "text": "仅写回份额 4 列，不重算 composite_prob/signal_level"},
        ],
    },
    "backfill_missing_shares": {
        "label": "补全缺失份额",
        "exclusive": False,
        "defaults": {},
        "data_flow": [
            {"step": "derive", "text": "扫描 etf_daily 缺份额的标的/日期（远端拉失败、T+1 发布拉空等成因）"},
            {"step": "fetch", "text": "仅对缺失标的拉取对应日期份额"},
            {"step": "write", "text": "写回份额 4 列，已有数据不覆盖"},
        ],
    },
    "fetch_sentiment": {
        "label": "拉取市场情绪",
        "exclusive": False,
        "defaults": {"days": SENTIMENT_BACKFILL_DAYS, "force": False, "start_date": None, "end_date": None},
        "data_flow": [
            {"step": "fetch", "text": "拉取沪深两市成交额 + 融资余额"},
            {
                "step": "write",
                "text": "写入情绪表，已入库日期跳过；情绪页曲线与买卖点 60 日分位（t_pct/m_pct）查询时计算",
            },
        ],
    },
    "fetch_etf_latest": {
        "label": "刷新最新ETF数据",
        "exclusive": False,
        "defaults": {},
        "data_flow": [
            {"step": "fetch", "text": "拉取最新交易日 K 线 + 份额（份额 T+1 自动回溯）"},
            {"step": "derive", "text": "完整指标链：量能/方向/位置/份额 → 综合概率 → 信号"},
            {"step": "write", "text": "upsert 当日行到 etf_daily"},
        ],
    },
    "recalc_composite": {
        "label": "重算综合概率(当前算法对齐)",
        "exclusive": False,
        "defaults": {},
        "data_flow": [
            {
                "step": "offline",
                "text": "全量读取行内 change_pct/volume_ratio/idx_chg + 前5日收盘，按当前算法重算 dir_prob → composite_prob",
            },
            {"step": "write", "text": "更新 dir_prob / composite_prob / signal_level 三列（幂等，可重复执行）"},
        ],
    },
    "rebuild_all": {
        "label": "一键重建全部数据",
        "exclusive": True,
        "defaults": {
            "etf_days": DEFAULT_ETF_SEED_DAYS,
            "shares_days": DEFAULT_SHARES_BACKFILL_DAYS,
            "sentiment_days": SENTIMENT_BACKFILL_DAYS,
            "force": False,
            "start_date": None,
            "end_date": None,
            "chunk_days": DEFAULT_CHUNK_DAYS,
        },
        "data_flow": [
            {"step": "fetch", "text": "按 交易日历 → ETF日度 → 份额 → 市场情绪 顺序全量拉取"},
            {"step": "derive", "text": "完整加工链：量能/方向/位置/份额 → 综合概率 → 信号"},
            {"step": "write", "text": "全表 upsert，已存在的日期跳过（勾选强制则覆盖）"},
        ],
    },
}

JOB_FNS: dict[str, Callable[..., dict]] = {
    "sync_calendar": job_sync_calendar,
    "backfill_etf_daily": job_backfill_etf_daily,
    "backfill_shares": job_backfill_shares,
    "backfill_missing_shares": job_backfill_missing_shares,
    "fetch_sentiment": job_fetch_sentiment,
    "fetch_etf_latest": job_fetch_etf_latest,
    "recalc_composite": job_recalc_composite,
    "rebuild_all": job_rebuild_all,
}
