// 市场情绪类型（情绪页）
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
  /** 缓存安全截止日: 增量接口 since 参数, 最近 N 个交易日不入缓存 */
  safe_end?: string
}

export interface SentimentRefreshResult {
  status: string
  turnover_days: number
  margin_days: number
  range: [string, string]
}
