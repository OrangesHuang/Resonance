// 盘中两市成交额类型
export interface IntradayTurnoverPoint {
  timestamp: string
  amount_yi: number
  est_amount_yi: number
}

export interface RealtimeTurnoverResponse {
  is_trading: boolean
  latest: IntradayTurnoverPoint | null
  percentile: number | null
  hist_days: number
  series: IntradayTurnoverPoint[]
  fetched_at: string
}
