// 信号/ETF/实时状态类型（大盘监控 + ETF 详情）
export interface EtfSignal {
  code: string
  name: string
  idx_name?: string
  price?: number
  close_price?: number
  change_pct: number
  volume_hand?: number
  volume?: number
  volume_ratio: number
  vol_prob: number
  dir_prob: number
  share_prob: number | null
  composite_prob: number
  signal_level: 'HIGH' | 'MID' | 'LOW'
  premium_pct?: number | null
  price_position?: number | null
  trade_direction?: string | null
  shares_yi?: number | null
  shares_delta_yi?: number | null
  shares_delta_pct?: number | null
  timestamp?: string
}

export interface SignalResponse {
  date: string
  mode: 'intraday' | 'daily' | 'none'
  updated_at: string | null
  etfs: EtfSignal[]
}

export interface KlinePoint {
  date: string
  open: number
  close: number
  high: number
  low: number
  volume: number
  ma250?: number | null
}

export interface ZoomWindow {
  start: number
  end: number
}

export interface DailySignal {
  date: string
  composite_prob: number | null
  volume_ratio: number | null
  signal_level: string | null
  price_position: number | null
  trade_direction: string | null
  shares_yi: number | null
  shares_delta_yi: number | null
  shares_delta_pct: number | null
  share_prob: number | null
}

export interface EtfHistoryResponse {
  code: string
  name: string
  idx: string
  kline: KlinePoint[]
  daily_signals: DailySignal[]
  /** 缓存安全截止日: 增量接口 since 参数, 最近 N 个交易日不入缓存 */
  safe_end?: string
}

export interface EtfInfo {
  code: string
  name: string
  idx: string
}

export interface RealtimeStatus {
  is_trading: boolean
  last_update: string | null
  server_time: string
  monitored_etfs: number
  has_signals: boolean
}

export interface StatsResponse {
  total_records: number
  trading_days: number
  date_range: [string | null, string | null]
  records_with_shares: number
  realtime_snapshot_count: number
}

export interface EtfRefreshResult {
  status: string
  count: number
  date: string | null
  shares?: {
    status: string
    shares_date: string | null
  } | null
}
