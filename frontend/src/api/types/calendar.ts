// 交易日历类型
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
