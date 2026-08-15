from __future__ import annotations

import os
from pathlib import Path

WORKSPACE = Path(os.environ.get("ETF_MONITOR_HOME", "~/.etf-monitor")).expanduser()
DB_PATH = WORKSPACE / "etf_monitor.db"

ETFS = {
    "510300": {"name": "华泰柏瑞沪深300ETF", "idx": "沪深300", "market": "sh"},
    "510050": {"name": "华夏上证50ETF", "idx": "上证50", "market": "sh"},
    "510500": {"name": "华泰柏瑞中证500ETF", "idx": "中证500", "market": "sh"},
    "512100": {"name": "南方中证1000ETF", "idx": "中证1000", "market": "sh"},
    "588000": {"name": "华夏科创50ETF", "idx": "科创50", "market": "sh"},
    "589680": {"name": "鹏华科创综指ETF", "idx": "科创综指", "market": "sh"},
    "159780": {"name": "华宝中证双创50ETF", "idx": "双创50", "market": "sz"},
    "515080": {"name": "招商中证红利ETF", "idx": "中证红利", "market": "sh"},
    "159352": {"name": "南方中证A500ETF", "idx": "中证A500", "market": "sz"},
    "563300": {"name": "华泰柏瑞中证2000ETF", "idx": "中证2000", "market": "sh"},
}

INDEX_CODE = "sh000300"
INDEX_NAME = "沪深300"

DEFAULT_RESONANCE_CODE = "510300"

WEIGHT_VOLUME = 0.50
WEIGHT_DIRECTION = 0.20
WEIGHT_SHARES = 0.30

WEIGHT_VOLUME_DEGRADED = 0.70
WEIGHT_DIRECTION_DEGRADED = 0.30

# 综合概率 V2: 分层门控模型参数
COMPOSITE_VERSION = 2
COMPOSITE_VOLUME_FLOOR = 0.3  # 量能置信度下限(低量时保留30%方向偏离)
COMPOSITE_VOLUME_SPAN = 0.7  # 量能置信度跨度(高量时额外贡献70%)
COMPOSITE_AGREE_REWARD = 15.0  # 份额与方向一致时的最大增强
COMPOSITE_CONFLICT_PENALTY = 25.0  # 份额与方向矛盾时的最大惩罚(非对称)
COMPOSITE_PP_VOL_MAX = 20.0  # 价格位置×量能交互项最大调节幅度

SIGNAL_HIGH = 70.0
SIGNAL_MID = 50.0

VOLUME_MA_WINDOW = 20
KLINE_LIMIT = 60

POSITION_WINDOW = 60  # 价格位置回看窗口(交易日)
POSITION_LOW = 40.0  # 低位阈值: 低于此值视为区间低位
POSITION_HIGH = 70.0  # 高位阈值: 高于此值视为区间高位
VOLUME_ACTIVE_RATIO = 1.5  # 放量判定: 量比超过此值才判断吸筹/出货方向

MARKET_OPEN_HOUR, MARKET_OPEN_MIN = 9, 30
MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN = 15, 0
LUNCH_START_HOUR, LUNCH_START_MIN = 11, 30
LUNCH_END_HOUR, LUNCH_END_MIN = 13, 0
TRADING_MINUTES = 240

REALTIME_INTERVAL_SEC = 30
HTTP_TIMEOUT = 15
AKSHARE_TIMEOUT = 30
MAX_RETRY = 2

# 盘中两市成交额轮询(收盘前分析用)
MARKET_TURNOVER_SYMBOLS = "sh000001,sz399001"  # 上证指数+深证成指
TURNOVER_POLL_INTERVAL_SEC = 300  # 5 分钟一次

KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{limit},qfq"
KLINE_URL_RANGE = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{start},{end},{limit},qfq"  # 日期区间拉取(回填历史用)
REALTIME_URL = "http://qt.gtimg.cn/q={symbols}"
SINA_KLINE_URL = (
    "https://quotes.sina.cn/cn/api/json_v2.php/"
    "CN_MarketDataService.getKLineData"
    "?symbol={symbol}&scale=240&ma=no&datalen={limit}"
)

# 拉取限流: 防止频繁请求被远端封禁
KLINE_CACHE_TTL_SEC = 60  # K线内存缓存有效期(秒)
KLINE_FAIL_COOLDOWN_SEC = 30  # K线拉取失败后的冷却(秒, 冷却期内直接返回空)
FETCH_SLEEP_SEC = 0.3  # 相邻 ETF 拉取间隔(秒)
REFRESH_MIN_INTERVAL_SEC = 120  # 手动刷新接口最小间隔(秒)
SHARES_RETRY = 2  # 份额单日拉取失败重试次数
SHARES_RETRY_BACKOFF_SEC = 5  # 份额重试递进间隔基数(秒, 每次×递增)
SHARE_WINDOW = 10  # 份额概率双基准窗口: 当日 vs 前N日均值取强(持续吸筹放大)
SHARES_FAIL_PAUSE_AFTER = 3  # 连续失败达到此数后暂停
SHARES_FAIL_PAUSE_SEC = 60  # 连续失败暂停时长(秒, 给远端喘息)

# 市场情绪模块
SENTIMENT_MA_WINDOW = 5  # 成交额均线窗口
SENTIMENT_BACKFILL_DAYS = 190  # 启动回填交易日数(需覆盖K线窗口+分位数暖机)
SENTIMENT_FETCH_HOUR = 16  # 每日采集时(收盘后, 先抓成交额)
SENTIMENT_FETCH_MIN = 0
SENTIMENT_FETCH_NIGHT_HOUR = 21  # 晚间二次采集(融资T+1晚间发布, 确保当日入库)
SENTIMENT_FETCH_NIGHT_MIN = 0
MARGIN_USE_SSE_FALLBACK = False  # True 则融资数据仅取上交所(更快但非两市合并)
VOLUME_UP_RATIO = 1.05  # 量比≥此值判为放量
VOLUME_DOWN_RATIO = 0.95  # 量比≤此值判为缩量

# 情绪分区(危险区/中性区/安全区)
SENTIMENT_ZONE_WINDOW = 60  # 分位数滚动窗口(交易日)
SENTIMENT_ZONE_MIN_PTS = 20  # 分位数计算最少样本数
SENTIMENT_ZONE_P_HIGH = 80.0  # 高分位阈值(≥判为过热)
SENTIMENT_ZONE_P_LOW = 20.0  # 低分位阈值(≤判为冷清)

# 防御型资产: 市场情绪两盏灯反转(成交额越热/融资越高→绿灯避险流入, 越冷→红灯)
# 中证红利(515080): 防御属性, 资金越涌向红利=避险情绪越强, 高热度是正面信号
DEFENSIVE_ETFS = {"515080"}

# 多指标共振模块
SHARE_PROB_RED = 30.0  # 份额概率≤此值→净赎回(红灯)
SHARE_PROB_GREEN = 65.0  # 份额概率≥此值→净申购(绿灯)
SHARE_LOW_FLIP_PP = 50.0  # 低位流出诱空翻转阈值: pp≤此值且净赎回→转吸筹灯(与composite一致)
SHARE_HIGH_FLIP_PP = 70.0  # 高位申购诱多翻转阈值: pp≥此值且净申购→转出货灯(后10日上涨仅46-50%, pp65-70仍72%真吸筹)
COMPOSITE_PROB_RED = 35.0  # 综合概率≤此值→出货信号(红灯)
COMPOSITE_PROB_GREEN = 45.0  # 综合概率≥此值→吸筹信号(绿灯)
RESONANCE_VERDICT_N = 3  # 同色灯≥此数→共振判定

# 交易日历模块
CALENDAR_SYNC_HOUR = 20  # 每周同步时
CALENDAR_SYNC_MIN = 0
CALENDAR_SYNC_DOW = "sun"  # 每周同步日(日历极少变化,周更即可)

# 数据管理 / 回填模块
DEFAULT_ETF_SEED_DAYS = 160  # 一键重建: ETF 日度回填交易日数
DEFAULT_SHARES_BACKFILL_DAYS = 140  # 一键重建: 份额回填交易日数
SEED_MIN_BARS = 20  # 种子化所需最少K线数
BACKFILL_SLEEP_SEC = 0.15  # 份额逐日回填间隔(秒)
TURNOVER_FETCH_SLEEP_SEC = 0.1  # 成交额逐日akshare间隔(秒,限流保护)
JOB_LIST_LIMIT = 30  # /api/data/jobs 返回的最大历史条数
JOB_DAYS_MAX = 1000  # 回填深度参数上限
DEFAULT_CHUNK_DAYS = 10  # 渐进式回填: 每批处理的交易日数(分批入库 + 按批上报进度)
