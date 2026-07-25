import os
from pathlib import Path

WORKSPACE = Path(os.environ.get("ETF_MONITOR_HOME", "~/.etf-monitor")).expanduser()
DB_PATH = WORKSPACE / "etf_monitor.db"

ETFS = {
    "510300": {"name": "华泰柏瑞沪深300ETF", "idx": "沪深300", "market": "sh"},
    "510310": {"name": "易方达沪深300ETF", "idx": "沪深300", "market": "sh"},
    "510330": {"name": "华夏沪深300ETF", "idx": "沪深300", "market": "sh"},
    "159919": {"name": "嘉实沪深300ETF", "idx": "沪深300", "market": "sz"},
    "510050": {"name": "华夏上证50ETF", "idx": "上证50", "market": "sh"},
    "510500": {"name": "华泰柏瑞中证500ETF", "idx": "中证500", "market": "sh"},
    "512100": {"name": "南方中证1000ETF", "idx": "中证1000", "market": "sh"},
    "588000": {"name": "华夏科创50ETF", "idx": "科创50", "market": "sh"},
    "589680": {"name": "鹏华科创综指ETF", "idx": "科创综指", "market": "sh"},
    "515080": {"name": "招商中证红利ETF", "idx": "中证红利", "market": "sh"},
}

INDEX_CODE = "sh000300"
INDEX_NAME = "沪深300"

WEIGHT_VOLUME = 0.50
WEIGHT_DIRECTION = 0.20
WEIGHT_SHARES = 0.30

WEIGHT_VOLUME_DEGRADED = 0.70
WEIGHT_DIRECTION_DEGRADED = 0.30

SIGNAL_HIGH = 70.0
SIGNAL_MID = 50.0

VOLUME_MA_WINDOW = 20
KLINE_LIMIT = 60

POSITION_WINDOW = 60        # 价格位置回看窗口(交易日)
POSITION_LOW = 40.0         # 低位阈值: 低于此值视为区间低位
POSITION_HIGH = 70.0        # 高位阈值: 高于此值视为区间高位
VOLUME_ACTIVE_RATIO = 1.5   # 放量判定: 量比超过此值才判断吸筹/出货方向

MARKET_OPEN_HOUR, MARKET_OPEN_MIN = 9, 30
MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN = 15, 0
LUNCH_START_HOUR, LUNCH_START_MIN = 11, 30
LUNCH_END_HOUR, LUNCH_END_MIN = 13, 0
TRADING_MINUTES = 240

REALTIME_INTERVAL_SEC = 30
HTTP_TIMEOUT = 15
AKSHARE_TIMEOUT = 30
MAX_RETRY = 2

KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{limit},qfq"
REALTIME_URL = "http://qt.gtimg.cn/q={symbols}"
