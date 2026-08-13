"""定时任务注册表:任务 id → 元信息(label/schedule/purpose/data_flow)。

与 tasks.py 的 start_scheduler 中注册的定时任务一一对应;schedule 为人类可读的
调度描述,data_flow 说明任务运行后拉取/加工/写入什么数据,供前端「定时任务」
页展示,让人一眼看清系统背后在做什么。
"""

from __future__ import annotations

SCHEDULED_DEFS: dict[str, dict] = {
    "realtime_poll": {
        "label": "盘中实时轮询",
        "schedule": "每 30 秒 · 仅交易时段",
        "purpose": "拉取 10 只监控 ETF + 沪深300 指数的实时行情,生成盘中信号快照",
        "data_flow": [
            {"step": "fetch", "text": "腾讯实时行情(价格/涨跌幅/成交量/开高低/昨收)"},
            {"step": "derive", "text": "盘中信号:U型修正量比、量能/方向/份额概率、综合概率、溢价率、价格位置"},
            {"step": "write", "text": "etf_realtime 快照表(保留 7 天)+ 内存最新信号"},
        ],
    },
    "turnover_poll": {
        "label": "盘中成交额轮询",
        "schedule": "每 5 分钟 · 仅交易时段",
        "purpose": "跟踪两市当日累计成交额,U型修正预估全天成交额",
        "data_flow": [
            {"step": "fetch", "text": "腾讯实时行情(上证指数 + 深证成指的成交额)"},
            {"step": "derive", "text": "按交易时段进度 U 型修正 → 全天成交额预估"},
            {"step": "write", "text": "intraday_turnover 表(当日累计 + 预估值)"},
        ],
    },
    "intraday_update": {
        "label": "盘中信号入库",
        "schedule": "每 15 分钟 · 仅交易时段",
        "purpose": "把最新盘中信号写入 etf_daily 当日行,让 K 线图当日可见",
        "data_flow": [
            {"step": "derive", "text": "内存最新信号(不触网)"},
            {"step": "write", "text": "etf_daily 当日行 upsert(OHLC + 因子 + 综合概率)"},
        ],
    },
    "preload_kline": {
        "label": "K线预载",
        "schedule": "工作日 09:00 · 开盘前",
        "purpose": "开盘前把本地库 K 线载入内存缓存,盘中轮询无需触网",
        "data_flow": [
            {"step": "read", "text": "etf_daily 各 ETF 近 60 日 K 线(不触网)"},
            {"step": "write", "text": "内存 K 线缓存,供盘中量比/概率计算使用"},
        ],
    },
    "daily_analysis": {
        "label": "日度分析",
        "schedule": "工作日 15:30 · 收盘后",
        "purpose": "收盘后拉取当日 K 线并跑完整指标链,写入历史日表",
        "data_flow": [
            {"step": "fetch", "text": "腾讯日 K 线(10 只 ETF + 沪深300 指数,前复权 OHLCV)"},
            {"step": "derive", "text": "量能链 volume_ratio→vol_prob、方向链 dir_prob、价格位置、综合概率 V2 四层门控"},
            {"step": "write", "text": "etf_daily 当日行 upsert(份额待份额任务补齐)"},
        ],
    },
    "fetch_sentiment": {
        "label": "市场情绪抓取",
        "schedule": "工作日 16:00 · 收盘后",
        "purpose": "拉取当日两市成交额,供情绪曲线与量比分位",
        "data_flow": [
            {"step": "fetch", "text": "akshare 沪深两市成交额(已入库日期跳过,边拉边写)"},
            {"step": "write", "text": "market_turnover 表"},
        ],
    },
    "fetch_shares": {
        "label": "份额抓取",
        "schedule": "工作日 19:30",
        "purpose": "拉取沪深交易所 T+1 发布的 ETF 份额,计算净申购/赎回",
        "data_flow": [
            {"step": "fetch", "text": "上交所官方接口 + 深交所 akshare 份额(当日未发布自动回溯)"},
            {"step": "derive", "text": "与前一交易日差分 → delta_yi / delta_pct → share_prob"},
            {"step": "write", "text": "etf_daily 份额 4 列写回,并回填日度行的份额"},
        ],
    },
    "fetch_sentiment_night": {
        "label": "晚间融资抓取",
        "schedule": "工作日 21:00",
        "purpose": "融资数据 T+1 晚间发布,二次抓取确保当日数据入库",
        "data_flow": [
            {"step": "fetch", "text": "akshare 两市融资余额 / 净融资买入"},
            {"step": "write", "text": "margin_trading 表"},
        ],
    },
    "sync_calendar": {
        "label": "交易日历同步",
        "schedule": "每周日 20:00",
        "purpose": "同步 A 股交易日历(极少变化,周更即可)",
        "data_flow": [
            {"step": "fetch", "text": "远端 A 股交易日历(历史 + 未来休市安排)"},
            {"step": "write", "text": "trade_calendar 表,供回填/定时任务判定交易日"},
        ],
    },
    "cleanup": {
        "label": "实时数据清理",
        "schedule": "每天 02:00",
        "purpose": "定期清理盘中快照,控制数据库体积",
        "data_flow": [
            {"step": "delete", "text": "删除 7 天前的 etf_realtime 快照记录"},
        ],
    },
}
