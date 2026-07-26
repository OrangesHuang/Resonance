export const WEEK_HEADERS = ['日', '一', '二', '三', '四', '五', '六']

export type DayKind = 'trading' | 'weekend' | 'holiday' | 'out'

export function pad(n: number): string {
  return String(n).padStart(2, '0')
}

export function toKey(year: number, month: number, day: number): string {
  return `${year}-${pad(month)}-${pad(day)}`
}

export function buildMonthCells(year: number, month: number): Array<number | null> {
  const firstDow = new Date(year, month - 1, 1).getDay()
  const daysInMonth = new Date(year, month, 0).getDate()
  return [
    ...Array<number | null>(firstDow).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]
}

export function classifyDay(
  dateStr: string,
  dow: number,
  tradingSet: Set<string>,
  lo: string | null,
  hi: string | null,
): DayKind {
  if (dow === 0 || dow === 6) return 'weekend'
  if (tradingSet.has(dateStr)) return 'trading'
  const inCoverage = (!lo || dateStr >= lo) && (!hi || dateStr <= hi)
  return inCoverage ? 'holiday' : 'out'
}

export const KIND_LABEL: Record<DayKind, string> = {
  trading: '交易日',
  weekend: '周末',
  holiday: '休市',
  out: '',
}
