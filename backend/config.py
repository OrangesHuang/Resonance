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

DEFAULT_RESONANCE_CODE = "510300"

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

# 市场情绪模块
SENTIMENT_MA_WINDOW = 5          # 成交额均线窗口
SENTIMENT_BACKFILL_DAYS = 190    # 启动回填交易日数(需覆盖K线窗口+分位数暖机)
SENTIMENT_FETCH_HOUR = 16        # 每日采集时(收盘后)
SENTIMENT_FETCH_MIN = 0
MARGIN_USE_SSE_FALLBACK = False  # True 则融资数据仅取上交所(更快但非两市合并)
VOLUME_UP_RATIO = 1.05           # 量比≥此值判为放量
VOLUME_DOWN_RATIO = 0.95         # 量比≤此值判为缩量

# 情绪分区(危险区/中性区/安全区)
SENTIMENT_ZONE_WINDOW = 60       # 分位数滚动窗口(交易日)
SENTIMENT_ZONE_MIN_PTS = 20      # 分位数计算最少样本数
SENTIMENT_ZONE_P_HIGH = 80.0     # 高分位阈值(≥判为过热)
SENTIMENT_ZONE_P_LOW = 20.0      # 低分位阈值(≤判为冷清)

# 多指标共振模块
SHARE_PROB_RED = 30.0            # 份额概率≤此值→净赎回(红灯)
SHARE_PROB_GREEN = 65.0          # 份额概率≥此值→净申购(绿灯)
RESONANCE_VERDICT_N = 3          # 同色灯≥此数→共振判定

# 交易日历模块
CALENDAR_SYNC_HOUR = 20          # 每周同步时
CALENDAR_SYNC_MIN = 0
CALENDAR_SYNC_DOW = "sun"        # 每周同步日(日历极少变化,周更即可)
