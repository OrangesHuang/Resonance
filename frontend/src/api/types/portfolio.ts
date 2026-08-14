// 组合回测类型
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
  kind: 'BUY' | 'SELL' | 'TRIM' | 'REFILL'
  kind_label: string
  price: number
  amount: number
  weight_pct: number
}

export interface PortfolioOpenPosition {
  code: string
  name: string
  buy_date: string
  market_value: number
  weight_pct: number
}

export interface PortfolioEtfSeries {
  code: string
  name: string
  nav: (number | null)[]
  delta: (number | null)[]
  trades: { date: string; action: string }[]
}

export interface PortfolioBacktestResponse {
  initial_capital: number
  initial_nav_per_share: number
  total_return_pct: number
  max_drawdown_pct: number
  empty_days: number
  empty_days_pct: number
  final_nav: number
  final_nav_per_share: number
  signal_count: number
  curve: PortfolioCurvePoint[]
  trades: PortfolioTrade[]
  open_positions: PortfolioOpenPosition[]
  etf_series: PortfolioEtfSeries[]
}
