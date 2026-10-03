// 一级退出监测: 解禁 / 减持 / IPO 供给

export interface UnlockWeek {
  week_start: string
  market_value_yi: number
  count: number
  by_board: Record<string, number>
}

export interface UnlockItem {
  date: string
  code: string
  name: string | null
  board: string
  unlock_type: string | null
  market_value_yi: number | null
  ratio_pct: number | null
  pre20_chg: number | null
}

export interface ReductionItem {
  code: string
  name: string | null
  board: string
  amount_yi: number
  count: number
}

export interface IpoMonth {
  month: string
  count: number
  funds_yi: number
}

export interface SupplyOverview {
  today: string
  updated: string | null
  unlock: {
    forward_weeks: UnlockWeek[]
    total_forward_yi: number
    horizon: string
    top: UnlockItem[]
  }
  reduction: {
    days: number
    total_yi: number
    count: number
    top: ReductionItem[]
  }
  ipo: {
    months: IpoMonth[]
    total_funds_yi: number
  }
}
