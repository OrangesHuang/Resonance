export interface DateWindow {
  start: string
  end: string
}

export const DEFAULT_VISIBLE_BARS = 120

export function windowToZoom(
  dates: string[],
  win: DateWindow | null,
  defaultVisible?: number,
): { start: number; end: number } {
  const len = dates.length
  if (len <= 1) return { start: 0, end: 100 }
  if (!win) {
    if (!defaultVisible || defaultVisible >= len) return { start: 0, end: 100 }
    return { start: ((len - defaultVisible) / (len - 1)) * 100, end: 100 }
  }
  let s = dates.findIndex(d => d >= win.start)
  if (s === -1) s = len - 1
  let e = len - 1
  while (e > s && dates[e] > win.end) e--
  return { start: (s / (len - 1)) * 100, end: (e / (len - 1)) * 100 }
}

export function zoomToWindow(dates: string[], startPct: number, endPct: number): DateWindow | null {
  const len = dates.length
  if (len === 0) return null
  const s = Math.max(0, Math.min(len - 1, Math.round((startPct / 100) * (len - 1))))
  const e = Math.max(s, Math.min(len - 1, Math.round((endPct / 100) * (len - 1))))
  return { start: dates[s], end: dates[e] }
}
