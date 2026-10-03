// ETF 动态管理（清单增删 + 数据覆盖状态）

export interface EtfCoverage {
  first_date: string | null
  last_date: string | null
  daily_rows: number
  shares_last_date: string | null
  adjust_events: number
  realtime_rows: number
  realtime_last: string | null
}

export interface EtfManageRow {
  code: string
  name: string
  idx: string
  market: string
  created_at: string | null
  coverage: EtfCoverage
  protected: boolean
  strategy_versions: string[]
  active_job: boolean
}

export interface EtfValidateResult {
  code: string
  name: string
  market: string
  idx: string
}

export interface EtfAddResult {
  code: string
  name: string
  idx: string
  market: string
}

export interface EtfDeleteResult {
  code: string
  daily_rows: number
  realtime_rows: number
  slots_refresh_job: string | null
}
