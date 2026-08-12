import type { KlinePoint, TradePoint, DailySignal } from '../../api/types'

export interface RangeStats {
  start: string
  end: string
  start_close: number
  end_close: number
  change_pct: number
  high: number
  high_date: string
  low: number
  low_date: string
  amplitude_pct: number
  buy_count: number
  sell_count: number
  range_return_pct: number | null
  open_position: boolean
  net_flow_yi: number | null
  flow_days: number
}

export function computeRangeStats(kline: KlinePoint[], trades: TradePoint[],
                                  start: string, end: string,
                                  signals?: DailySignal[]): RangeStats | null {
  const idxStart = kline.findIndex(k => k.date === start)
  const idxEnd = kline.findIndex(k => k.date === end)
  if (idxStart < 0 || idxEnd < 0 || idxEnd < idxStart) return null
  const seg = kline.slice(idxStart, idxEnd + 1)

  const startClose = seg[0].close
  const endClose = seg[seg.length - 1].close
  let high = seg[0].high
  let highDate = seg[0].date
  let low = seg[0].low
  let lowDate = seg[0].date
  for (const k of seg) {
    if (k.high > high) { high = k.high; highDate = k.date }
    if (k.low < low) { low = k.low; lowDate = k.date }
  }

  const inRange = trades.filter(t => t.date >= start && t.date <= end)
  const buys = inRange.filter(t => t.action === 'BUY')
  const sells = inRange.filter(t => t.action === 'SELL')

  // 区间策略收益: 区间内 BUY→SELL 配对, 未平仓按末日收盘计
  let ret = 1.0
  let openPos = false
  let buyPrice: number | null = null
  for (const t of inRange) {
    if (t.action === 'BUY') {
      buyPrice = t.price
      openPos = true
    } else if (t.action === 'SELL' && buyPrice != null) {
      ret *= t.price / buyPrice
      buyPrice = null
      openPos = false
    }
  }
  if (buyPrice != null && buyPrice > 0) {
    ret *= endClose / buyPrice
  }

  // 区间累计净申赎: 区间内各日 shares_delta_yi 求和(缺失日跳过)
  let netFlow: number | null = null
  let flowDays = 0
  if (signals) {
    const sigByDate = new Map(signals.map(s => [s.date, s]))
    netFlow = 0
    for (const k of seg) {
      const v = sigByDate.get(k.date)?.shares_delta_yi
      if (v == null) continue
      netFlow += v
      flowDays += 1
    }
  }

  return {
    start, end,
    start_close: startClose,
    end_close: endClose,
    change_pct: (endClose / startClose - 1) * 100,
    high, high_date: highDate,
    low, low_date: lowDate,
    amplitude_pct: (high / low - 1) * 100,
    buy_count: buys.length,
    sell_count: sells.length,
    range_return_pct: (ret - 1) * 100,
    open_position: openPos,
    net_flow_yi: netFlow,
    flow_days: flowDays,
  }
}
