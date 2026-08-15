import type { KlinePoint, ResonanceHistoryPoint } from '../../api/types'

/** 五图统一日期轴: 多组日期求并集并升序。
 *
 *  共振页各图数据范围不一致(如 515080: K线 631 天 vs 共振 453 天,
 *  情绪成交额 472 天), 缩放按百分比广播到不同长度的数组会错位
 *  ("无法缩放"); 统一到同一日期轴后百分比窗口即逐日对齐。
 */
export function unionDates(groups: string[][]): string[] {
  const set = new Set<string>()
  for (const group of groups) {
    for (const d of group) set.add(d)
  }
  return [...set].sort()
}

/** K线对齐(兜底): 缺失日期用最近的真实收盘价平铺。
 *  不能补 0(会把 y 轴 scale 拉到 0, 真实蜡烛被压扁)、
 *  不能补 null/candlestick 数据项为 null 会直接报错;
 *  平铺收盘价在视觉上是水平线, 不影响缩放对齐。
 *  注意: 共振历史按 klineStart 过滤后是 K线日期子集, 正常不会触发。
 */
export function alignKlineToDates(kline: KlinePoint[], dates: string[]): KlinePoint[] {
  const byDate = new Map(kline.map(k => [k.date, k]))
  const firstClose = kline.length ? kline[0].close : 0
  const lastClose = kline.length ? kline[kline.length - 1].close : 0
  const firstDate = kline.length ? kline[0].date : ''
  return dates.map(d => {
    const k = byDate.get(d)
    if (k) return k
    const close = d < firstDate ? firstClose : lastClose
    return { date: d, open: close, close, high: close, low: close, volume: 0 }
  })
}

/** 共振历史对齐: 缺失日期补中性点(0 盏灯/全灰)。
 *  红绿灯图柱高为 0 不绘制, 热力图 state 缺省为 gray, 语义为"无数据"。 */
export function alignResonanceHistoryToDates(
  history: ResonanceHistoryPoint[],
  dates: string[],
): ResonanceHistoryPoint[] {
  const byDate = new Map(history.map(h => [h.date, h]))
  return dates.map(d => byDate.get(d) ?? { date: d, red: 0, green: 0, states: {} })
}
