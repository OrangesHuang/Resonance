// 交易日历类型
export interface CalendarDays {
  year: number
  days: string[]
  total: number
  range: [string | null, string | null]
  updated_at: string | null
  today: string
  // 数据槽位台账: {date: 0-4} — etf_daily/份额/成交额/融资 四源覆盖数; slot_start = 槽位起始日期
  coverage?: Record<string, number>
  slot_start?: string | null
}

export interface CalendarRefreshResult {
  status: string
  count: number
  range: [string | null, string | null]
}
