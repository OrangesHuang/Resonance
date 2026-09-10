import type { KlinePoint } from '../../api/types'

/**
 * 标准 MACD 三件套 (DIF 12/26 + DEA + 红绿柱) 的计算与主图下方独立面板构建。
 *
 * 认知:
 *  - MA250 是"价格水平的平滑"(绝对值, 贴价走); MACD 是"两条 EMA 的差"(动量/乖离,
 *    围绕 0 正负振荡)。两者属性不同, 柱状图(dif-dea)*2 只有放在独立面板、以 0 为
 *    中轴才有意义, 叠在价格轴上会与 K 线量纲错位而不可读。
 *  - DIF 金叉/死叉 DEA 是经典短线进出参考, 用于观察快慢周期动量切换。
 */

const MACD_FAST = 12
const MACD_SLOW = 26
const MACD_SIGNAL = 9

export const DIF_COLOR = '#22d3ee' // DIF(12,26) 青色
export const DEA_COLOR = '#fbbf24' // 信号线 DEA(9) 黄色
const HIST_UP = '#ef4444' // 红柱: DIF > DEA (多头)
const HIST_DOWN = '#22c55e' // 绿柱: DIF < DEA (空头)
const AXIS_LABEL = '#6b7280'

function ema(vals: number[], span: number): number[] {
  const k = 2 / (span + 1)
  let e: number | null = null
  return vals.map(v => {
    e = e == null ? v : v * k + e * (1 - k)
    return e
  })
}

export interface MacdResult {
  dif: number[]
  dea: number[]
  hist: number[]
}

export function computeMacd(closes: number[], fast = MACD_FAST, slow = MACD_SLOW, signal = MACD_SIGNAL): MacdResult {
  const ef = ema(closes, fast)
  const es = ema(closes, slow)
  const dif = closes.map((_, i) => ef[i] - es[i])
  const dea = ema(dif, signal)
  const hist = dif.map((v, i) => (v - dea[i]) * 2)
  return { dif, dea, hist }
}

/**
 * 构建 MACD 独立面板(主图下方)所需的部分 option:
 *  - grid 行(第 4 列, gridIndex 4)
 *  - xAxis 条目(gridIndex 4)
 *  - yAxis 条目(gridIndex 4, 以 0 为中轴)
 *  - series 数组(红绿柱 + DIF + DEA, 0 线参考)
 *
 * series 需追加到末尾; 网格/坐标轴由调用方并入对应数组。
 */
export function buildMacdPanel(kline: KlinePoint[], dates: string[]) {
  const closes = kline.map(k => k.close)
  const { dif, dea, hist } = computeMacd(closes)
  const histData = hist.map(v => ({
    value: v,
    itemStyle: { color: v >= 0 ? HIST_UP : HIST_DOWN },
  }))

  return {
    grid: { left: 60, right: 20, top: '74%', height: '11%' },
    xAxis: { type: 'category' as const, data: dates, gridIndex: 4, boundaryGap: true, axisLabel: { show: false } },
    yAxis: {
      scale: true,
      gridIndex: 4,
      splitNumber: 3,
      splitLine: { show: false },
      axisLabel: { color: AXIS_LABEL, fontSize: 9 },
    },
    series: [
      {
        name: 'MACD柱',
        type: 'bar' as const,
        data: histData,
        xAxisIndex: 4,
        yAxisIndex: 4,
        barWidth: '60%',
        silent: true,
      },
      {
        name: `DIF(${MACD_FAST},${MACD_SLOW})`,
        type: 'line' as const,
        data: dif,
        xAxisIndex: 4,
        yAxisIndex: 4,
        showSymbol: false,
        silent: true,
        lineStyle: { width: 1.3, color: DIF_COLOR },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#4b5563', width: 1 },
          data: [{ yAxis: 0 }],
        },
      },
      {
        name: `DEA(${MACD_SIGNAL})`,
        type: 'line' as const,
        data: dea,
        xAxisIndex: 4,
        yAxisIndex: 4,
        showSymbol: false,
        silent: true,
        lineStyle: { width: 1.3, color: DEA_COLOR },
      },
    ],
  }
}

/**
 * 主 K 线面板(gridIndex 0)右轴上的 DIF/DEA 叠加线。
 * 用于在价格图上直接观察两条线的交叉(金叉/死叉), 与下方子面板互为补充。
 * 需在 series 末尾追加; 右轴(索引 5)由调用方并入 yAxis。
 */
export function buildMacdOverlay(kline: KlinePoint[]) {
  const closes = kline.map(k => k.close)
  const { dif, dea } = computeMacd(closes)
  return {
    yAxis: {
      scale: true,
      gridIndex: 0,
      position: 'right' as const,
      splitLine: { show: false },
      axisLabel: { show: false },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        name: `DIF(${MACD_FAST},${MACD_SLOW})`,
        type: 'line' as const,
        data: dif,
        xAxisIndex: 0,
        yAxisIndex: 5,
        showSymbol: false,
        silent: true,
        lineStyle: { width: 1.1, color: DIF_COLOR },
      },
      {
        name: `DEA(${MACD_SIGNAL})`,
        type: 'line' as const,
        data: dea,
        xAxisIndex: 0,
        yAxisIndex: 5,
        showSymbol: false,
        silent: true,
        lineStyle: { width: 1.1, color: DEA_COLOR },
      },
    ],
  }
}
