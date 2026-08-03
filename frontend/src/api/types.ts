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

export interface TurnoverPoint {
  date: string
  sh_amount_yi: number
  sz_amount_yi: number
  total_amount_yi: number
  ma5_yi: number | null
  vol_ratio: number | null
}

export interface MarginPoint {
  date: string
  fin_balance_yi: number
  loan_balance_yi: number | null
  fin_buy_yi: number | null
  net_fin_buy_yi: number | null
}

export type VolumeState = '放量' | '缩量' | '持平'

export interface TurnoverSummary {
  latest_date: string | null
  latest_yi: number | null
  ma5_yi: number | null
  vol_ratio: number | null
  volume_state: VolumeState | null
}

export interface MarginSummary {
  latest_date: string | null
  fin_balance_yi: number | null
  net_fin_buy_yi: number | null
  prev_fin_balance_yi: number | null
}

export type ZoneKey = 'danger' | 'neutral' | 'safe'
export type ZoneLevel = 'high' | 'mid' | 'low'

export interface ZoneIndicator {
  percentile: number
  level: ZoneLevel
}

export interface ZoneCurrent {
  date: string
  zone: ZoneKey
  label: string
  score: number
  window: number
  turnover: ZoneIndicator
  margin: ZoneIndicator
}

export interface ZonePoint {
  date: string
  zone: ZoneKey
  label: string
  score: number
}

export interface SentimentZone {
  current: ZoneCurrent | null
  history: ZonePoint[]
}

export interface SentimentOverview {
  turnover: TurnoverPoint[]
  margin: MarginPoint[]
  summary: {
    turnover: TurnoverSummary | null
    margin: MarginSummary | null
  }
  zone: SentimentZone
  updated_at: string | null
}

export interface SentimentRefreshResult {
  status: string
  turnover_days: number
  margin_days: number
  range: [string, string]
}

export type LightState = 'red' | 'green' | 'gray'

export interface ResonanceIndicator {
  key: string
  name: string
  group: 'etf' | 'market'
  state: LightState
  value: number | string | null
  display: string
  note: string
}

export interface ResonanceHistoryPoint {
  date: string
  red: number
  green: number
  states: Record<string, LightState>
}

export interface ResonanceOverview {
  code: string
  name: string
  date: string | null
  indicators: ResonanceIndicator[]
  red_count: number
  green_count: number
  gray_count: number
  total: number
  verdict: string
  history: ResonanceHistoryPoint[]
}

export interface IndicatorEvidence {
  method: string
  formula: string
  thresholds: string
  reason: string
  value: number | string | null
  inputs: Record<string, number | string | null>
  window?: number[]
  window_stats?: {
    count: number
    below: number
    equal: number
    min: number
    max: number
  }
  data_note?: string
}

export interface ResonanceDayIndicator extends ResonanceIndicator {
  evidence: IndicatorEvidence
}

export interface ResonanceDayDetail {
  code: string
  name: string
  date: string
  indicators: ResonanceDayIndicator[]
  red_count: number
  green_count: number
  gray_count: number
  total: number
  verdict: string
}

export interface TradePoint {
  date: string
  action: 'BUY' | 'SELL'
  price: number
  reason: string
}

export interface TradesResponse {
  code: string
  trades: TradePoint[]
}

export interface V3TradesResponse {
  code: string
  trades: TradePoint[]
  metrics: {
    total_return_pct: number
    round_count: number
    win_count: number
    win_rate: number
    trade_count: number
  }
  holding: boolean
}

export interface EtfRefreshResult {
  status: string
  count: number
  date: string | null
}

export interface CalendarDays {
  year: number
  days: string[]
  total: number
  range: [string | null, string | null]
  updated_at: string | null
  today: string
}

export interface CalendarRefreshResult {
  status: string
  count: number
  range: [string | null, string | null]
}

export type JobStatus = 'pending' | 'running' | 'success' | 'failed'

export type JobParam = string | number | boolean

export interface JobState {
  id: string
  task: string
  params: Record<string, JobParam>
  status: JobStatus
  current: number
  total: number
  message: string
  started_at: string | null
  finished_at: string | null
  error: string | null
  result: Record<string, unknown> | null
}

export interface JobDef {
  task: string
  label: string
  defaults: Record<string, number | boolean>
}

export interface EtfDailyStats {
  total_records: number
  trading_days: number
  date_range: [string | null, string | null]
  records_with_shares: number
}

export interface SeriesStats {
  count: number
  range: [string | null, string | null]
}

export interface CalendarStats {
  count: number
  range: [string | null, string | null]
  last_sync: string | null
}

export interface DataSources {
  etf_daily: EtfDailyStats
  turnover: SeriesStats
  margin: SeriesStats
  calendar: CalendarStats
}

export interface SchedulerJobInfo {
  id: string
  next_run: string | null
}

export interface DataStatus {
  sources: DataSources
  jobs: JobDef[]
  running: JobState[]
  scheduler: SchedulerJobInfo[]
  defaults: { etf_days: number; shares_days: number; sentiment_days: number }
}

export interface StartJobRequest {
  task: string
  params?: Record<string, JobParam>
}

export interface StartJobResponse {
  job_id: string
}

// ========== V2 信号系统 ==========

export interface V2AnomalyVector {
  vol: number
  price: number
  share: number
  breadth: number
  divergence: number
}

export interface V2SignalPoint {
  date: string
  close: number
  anomaly: V2AnomalyVector
  p_accum: number
  p_dist: number
  p_neutral: number
  signal: number
  match_accum: number
  match_dist: number
  regime: number
  regime_label: 'bull' | 'bear' | 'range'
}

export interface V2SignalsResponse {
  code: string
  regime: number
  regime_label: string
  latest: V2SignalPoint | null
  signal_count: number
  signals: V2SignalPoint[]
}

export interface V2DimensionDetail {
  key: string
  name: string
  score: number
  detail: string
}

export interface V2SignalDayDetail {
  date: string
  anomaly: V2AnomalyVector
  dimensions: V2DimensionDetail[]
  p_accum: number
  p_dist: number
  p_neutral: number
  signal: number
  match_accum: number
  match_dist: number
  regime: number
  regime_label: string
}

export interface V2RegimeResponse {
  code: string
  regime_score: number
  regime_label: string
  data_points: number
}

export interface V2BacktestMetrics {
  total_return: number
  annual_return: number
  annual_vol: number
  sharpe: number
  max_drawdown: number
  days: number
  exposure_pct: number
  trade_count: number
}

export interface V2BacktestTrade {
  date: string
  action: 'BUY' | 'SELL'
  from_pos: number
  to_pos: number
  signal: number
  price: number
  reason: string
}

export interface V2BacktestResponse {
  metrics: V2BacktestMetrics
  benchmark: V2BacktestMetrics
  trades: V2BacktestTrade[]
  equity_curve: { date: string; equity: number; position: number }[]
}

// ========== 组合回测 ==========

export interface PortfolioCurvePoint {
  date: string
  nav: number
  nav_per_share: number
  position_pct: number
}

export interface PortfolioTrade {
  date: string
  signal_date: string
  code: string
  name: string
  kind: 'BUY' | 'TOPUP' | 'REDUCE' | 'SELL'
  kind_label: string
  units: number
  price: number
  amount: number
}

export interface PortfolioOpenPosition {
  code: string
  name: string
  units: number
  buy_date: string
}

export interface PortfolioBacktestResponse {
  initial_capital: number
  initial_nav_per_share: number
  total_return_pct: number
  max_drawdown_pct: number
  avg_position_pct: number
  final_nav: number
  final_nav_per_share: number
  signal_count: number
  curve: PortfolioCurvePoint[]
  trades: PortfolioTrade[]
  open_positions: PortfolioOpenPosition[]
}
