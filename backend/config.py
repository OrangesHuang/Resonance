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

# 拉取限流: 防止频繁请求被远端封禁
KLINE_CACHE_TTL_SEC = 60      # K线内存缓存有效期(秒)
KLINE_FAIL_COOLDOWN_SEC = 30  # K线拉取失败后的冷却(秒, 冷却期内直接返回空)
FETCH_SLEEP_SEC = 0.3         # 相邻 ETF 拉取间隔(秒)
REFRESH_MIN_INTERVAL_SEC = 120  # 手动刷新接口最小间隔(秒)
SHARES_RETRY = 2              # 份额单日拉取失败重试次数
SHARES_RETRY_BACKOFF_SEC = 5  # 份额重试递进间隔基数(秒, 每次×递增)
SHARES_FAIL_PAUSE_AFTER = 3   # 连续失败达到此数后暂停
SHARES_FAIL_PAUSE_SEC = 60    # 连续失败暂停时长(秒, 给远端喘息)

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
COMPOSITE_PROB_RED = 35.0        # 综合概率≤此值→出货信号(红灯)
COMPOSITE_PROB_GREEN = 65.0      # 综合概率≥此值→吸筹信号(绿灯)
RESONANCE_VERDICT_N = 3          # 同色灯≥此数→共振判定

# 交易日历模块
CALENDAR_SYNC_HOUR = 20          # 每周同步时
CALENDAR_SYNC_MIN = 0
CALENDAR_SYNC_DOW = "sun"        # 每周同步日(日历极少变化,周更即可)

# 数据管理 / 回填模块
DEFAULT_ETF_SEED_DAYS = 160        # 一键重建: ETF 日度回填交易日数
DEFAULT_SHARES_BACKFILL_DAYS = 140 # 一键重建: 份额回填交易日数
SEED_MIN_BARS = 20                 # 种子化所需最少K线数
BACKFILL_SLEEP_SEC = 0.15          # 份额逐日回填间隔(秒)
TURNOVER_FETCH_SLEEP_SEC = 0.1     # 成交额逐日akshare间隔(秒,限流保护)
JOB_LIST_LIMIT = 30                # /api/data/jobs 返回的最大历史条数
JOB_DAYS_MAX = 1000                # 回填深度参数上限

# 交易策略 / 回测模块
STRATEGY_CODE = "510300"           # 默认策略标的
WARN_RED_N = 2                     # 红灯≥此数→预警
REENTRY_GREEN_N = 3                # 锁定后绿灯≥此数→计入复入连续天数
REENTRY_CONFIRM_DAYS = 2           # 连续N天满足复入条件→解锁
WARN_CONFIRM = 2                   # 预警确认次数(第N次预警触发减仓)
REDUCE_STEP = 0.20                 # 减仓幅度(从满仓减去)
BACKTEST_INIT_CAPITAL = 1_000_000  # 回测初始资金
BACKTEST_COST_RATE = 0.0           # 单边交易成本(万分之三=0.0003)
BACKTEST_RISK_FREE = 0.0           # 无风险利率(年化)
TRADING_DAYS_PER_YEAR = 244        # A股年交易日

# ========== V2 信号系统 ==========

# 市场状态检测 (Layer 0)
REGIME_MA_PERIOD = 200              # 长期均线周期
REGIME_EMA_SMOOTH = 20              # 状态分数平滑窗口
REGIME_BULL_THRESHOLD = 0.3         # 牛市判定阈值
REGIME_BEAR_THRESHOLD = -0.3        # 熊市判定阈值

# 异常度计算窗口 (Layer 1)
ANOMALY_VOL_WINDOW = 40             # 量能分布回看窗口（缩短以提高敏感度）
ANOMALY_SHARE_WINDOW = 60           # 份额分布回看窗口
ANOMALY_VOLATILITY_WINDOW = 20      # 波动率计算窗口
ANOMALY_BREADTH_WINDOW = 20         # 广度分布回看窗口
VOL_Z_SCALE = 0.5                   # 量能 z-score 缩放因子

# 特征向量 (Layer 2) — 5维: [量能, 价格, 份额, 广度, 背离]
ACCUM_SIGNATURE = [0.7, -0.5, 0.4, -0.3, 0.8]   # 吸筹特征
DIST_SIGNATURE  = [0.6,  0.5, -0.4, 0.3, -0.8]  # 出货特征

# 贝叶斯推断 (Layer 3)
SIGNATURE_LAMBDA = 5.0              # 似然比更新强度
# 不同市场状态下的先验概率 [P(吸筹), P(出货)]
PRIOR_BULL = [0.30, 0.10]           # 牛市中吸筹概率高于出货
PRIOR_BEAR = [0.10, 0.30]           # 熊市中出货概率高于吸筹
PRIOR_RANGE = [0.18, 0.18]          # 震荡市中两者等概率

# 决策层 (Layer 4)
SIGNAL_BUY_THRESHOLD = 0.75         # 买入信号强度阈值
SIGNAL_SELL_THRESHOLD = 0.75        # 卖出信号强度阈值
V2_POSITION_MAX = 3                 # 最大仓位份数
V2_POSITION_STEP = 1                # 单次调仓份数
V2_MIN_HOLD_DAYS = 15               # 最短持仓天数
V2_COOLDOWN_DAYS = 5                # 交易冷却期(防止信号扎堆)
V2_COST_RATE = 0.0003               # 单边交易成本(万分之三)
