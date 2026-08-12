import type { TradePoint } from '../../api/types'

export const BAND_GREEN = 'rgba(34, 197, 94, 0.10)'
export const BAND_RED = 'rgba(239, 68, 68, 0.10)'

export interface BandLabel {
  show: boolean
  position: 'insideTop'
  color: string
  fontSize: number
  formatter: string
}

const HOLD_LABEL: BandLabel = { show: true, position: 'insideTop', color: 'rgba(34, 197, 94, 0.5)', fontSize: 9, formatter: '安全区' }
const EMPTY_LABEL: BandLabel = { show: true, position: 'insideTop', color: 'rgba(239, 68, 68, 0.5)', fontSize: 9, formatter: '危险区' }

export interface TradeBandStart {
  xAxis: string
  itemStyle: { color: string }
  label?: BandLabel
}
export interface TradeBandEnd {
  xAxis: string
}

/** 清洗 markArea 数据: 过滤 null/undefined 项与 xAxis 不在轴内的项,
 *  避免 ECharts markAreaTransform 返回 undefined 后崩溃。 */
export function sanitizeBands(
  bands: Array<[TradeBandStart, TradeBandEnd] | Array<{ xAxis?: string; itemStyle?: object }>>,
  dates: string[],
): Array<[TradeBandStart, TradeBandEnd]> {
  return bands
    .filter((b): b is [TradeBandStart, TradeBandEnd] =>
      Array.isArray(b) && b.length === 2 && !!b[0] && !!b[1]
      && typeof b[0].xAxis === 'string' && typeof b[1].xAxis === 'string')
    .filter(b => dates.includes(b[0].xAxis) && dates.includes(b[1].xAxis))
}

export function buildTradeBands(trades: TradePoint[], lastDate: string): Array<[TradeBandStart, TradeBandEnd]> {
  // BUY→SELL 之间绿色蒙布(持仓区间), SELL→BUY 之间红色蒙布(空仓区间)
  const bands: Array<[TradeBandStart, TradeBandEnd]> = []
  let pendingBuy: string | null = null
  let lastSell: string | null = null

  for (const t of trades) {
    if (t.action === 'BUY') {
      if (lastSell) {
        bands.push([{ xAxis: lastSell, itemStyle: { color: BAND_RED }, label: EMPTY_LABEL }, { xAxis: t.date }])
        lastSell = null
      }
      pendingBuy = t.date
    } else if (t.action === 'SELL') {
      if (pendingBuy) {
        bands.push([{ xAxis: pendingBuy, itemStyle: { color: BAND_GREEN }, label: HOLD_LABEL }, { xAxis: t.date }])
        pendingBuy = null
      }
      lastSell = t.date
    }
  }
  // 未平仓: 最后一次买入延伸到最后一日
  if (pendingBuy && pendingBuy < lastDate) {
    bands.push([{ xAxis: pendingBuy, itemStyle: { color: BAND_GREEN }, label: HOLD_LABEL }, { xAxis: lastDate }])
  }
  return bands
}
