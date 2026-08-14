// 多指标共振类型（共振页）
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
