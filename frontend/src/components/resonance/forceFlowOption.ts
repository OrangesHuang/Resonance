import type { KlinePoint } from '../../api/types'

/**
 * 同花顺公式移植: 「主力进出 / 吸筹 / 散户线 / 庄家线」副图。
 *
 * 认知:
 *  - 这是同花顺常见的"主力资金"类公式: 用 LOW 相对前一日均价(VAR1)的偏离量,
 *    经 SMA/EMA 平滑出"主力进场/洗盘"柱; 另一套 Var 系列算出"吸筹"柱;
 *    再用 HHV/LLV 位置算"散户线", 用 RSV→K/D→J 的 EMA 算"庄家线"。
 *  - 变量名在原公式里重复声明(VAR1..VAR5 出现两次), 按顺序后者覆盖前者,
 *    本移植按执行顺序逐个计算, 不做重命名。
 *  - 原公式含 `IF(YEAR>=2038,0,1)` 的时间闸(2038 前恒为 1)与
 *    `IF(CLOSE*1.3,..)`(恒真) / `IF(MA(CLOSE,58),..)`(恒真) 等退化判断,
 *    移植时按当前取值(1 / 真分支)简化, 不引入时间硬编码。
 */

const UP = '#ef4444' // 红: 主力进场 / 吸筹
const DOWN = '#22c55e' // 绿: 洗盘
const RETAIL = '#facc15' // 散户线 (同花顺 ColorFFFF00)
const DEALER = '#e879f9' // 庄家线 (同花顺 colorff00ff)
const STRONG_BOUNDARY = 80 // 强弱分界

// ---- 同花顺公式原语(无 I/O 的纯函数) ----
function ref(a: number[], n: number): number[] {
  return a.map((_, i) => a[Math.max(0, i - n)])
}
function absA(a: number[]): number[] {
  return a.map(Math.abs)
}
function subA(a: number[], b: number[]): number[] {
  return a.map((v, i) => v - b[i])
}
function maxA(a: number[], b: number[] | number): number[] {
  return a.map((v, i) => Math.max(v, typeof b === 'number' ? b : b[i]))
}
function sma(a: number[], n: number, m: number): number[] {
  const out: number[] = []
  let prev = a[0] ?? 0
  for (let i = 0; i < a.length; i++) {
    prev = (m * a[i] + (n - m) * prev) / n
    out.push(prev)
  }
  return out
}
function ema(a: number[], n: number): number[] {
  const k = 2 / (n + 1)
  let prev = a[0] ?? 0
  return a.map(v => {
    prev = v * k + prev * (1 - k)
    return prev
  })
}
function llv(a: number[], n: number): number[] {
  return a.map((_, i) => {
    let m = Infinity
    for (let j = Math.max(0, i - n + 1); j <= i; j++) m = Math.min(m, a[j])
    return m
  })
}
function hhv(a: number[], n: number): number[] {
  return a.map((_, i) => {
    let m = -Infinity
    for (let j = Math.max(0, i - n + 1); j <= i; j++) m = Math.max(m, a[j])
    return m
  })
}
function divA(a: number[], b: number[]): number[] {
  return a.map((v, i) => (b[i] === 0 ? 0 : v / b[i]))
}

export interface ForceFlowResult {
  main: number[] // 主力进出 (VAR5)
  acc: number[] // 吸筹
  retail: number[] // 散户线
  dealer: number[] // 庄家线
  rsiCross: boolean[] // CROSS(85, RSI): RSI 自上而下跌破 85
}

export function computeForceFlow(kline: KlinePoint[]): ForceFlowResult {
  const O = kline.map(k => k.open)
  const H = kline.map(k => k.high)
  const L = kline.map(k => k.low)
  const C = kline.map(k => k.close)

  // 第一段: 主力进场/洗盘
  const avg4 = L.map((v, i) => (v + O[i] + C[i] + H[i]) / 4)
  const var1 = ref(avg4, 1)
  const var2 = divA(
    sma(absA(subA(L, var1)), 13, 1),
    sma(maxA(subA(L, var1), 0), 10, 1),
  )
  const var3 = ema(var2, 10)
  const var4 = llv(L, 33)
  const var5 = ema(L.map((v, i) => (v <= var4[i] ? var3[i] : 0)), 3)

  // RSI(3) 用于 CROSS(85, RSI) 的 ▼ 标记
  const lc = ref(C, 1)
  const dc = subA(C, lc)
  const rsi = divA(sma(maxA(dc, 0), 3, 1), sma(absA(dc), 3, 1)).map(v => v * 100)
  const rsiCross = rsi.map((v, i) => i > 0 && rsi[i - 1] > 85 && v <= 85)

  // 第二段: 吸筹 (Var1..Var8, 覆盖同名变量; 时间闸 2026<2038 恒为 1)
  const v2 = ref(L, 1)
  const v3 = divA(
    sma(absA(subA(L, v2)), 3, 1),
    sma(maxA(subA(L, v2), 0), 3, 1),
  ).map(v => v * 100)
  const v4 = ema(v3.map(v => v * 10), 3)
  const v5 = llv(L, 30)
  const v6 = hhv(v4, 30)
  const v8 = ema(
    L.map((v, i) => (v <= v5[i] ? (v4[i] + v6[i] * 2) / 2 : 0)),
    3,
  ).map(v => v / 618)
  const acc = v8.map(v => (v > 100 ? 100 : v))

  // 散户线: 收盘在 55 日高低区间中的位置(越靠低=散户越少/越安全)
  const hh55 = hhv(H, 55)
  const ll55 = llv(L, 55)
  const retail = hh55.map((h, i) => (h === ll55[i] ? 50 : (100 * (h - C[i])) / (h - ll55[i])))

  // 庄家线: RSV(34) → K/D → J → EMA(J,6)
  const hh34 = hhv(H, 34)
  const ll34 = llv(L, 34)
  const rsv = hh34.map((h, i) => (h === ll34[i] ? 50 : (100 * (C[i] - ll34[i])) / (h - ll34[i])))
  const kLine = sma(rsv, 3, 1)
  const dLine = sma(kLine, 3, 1)
  const jLine = kLine.map((k, i) => 3 * k - 2 * dLine[i])
  const dealer = ema(jLine, 6)

  return { main: var5, acc, retail, dealer, rsiCross }
}

/**
 * 构建"主力/吸筹/散户/庄家"独立副图(gridIndex 5)所需的部分 option。
 * series 需追加到末尾; 网格/坐标轴由调用方并入对应数组。
 */
export function buildForceFlowPanel(kline: KlinePoint[], dates: string[]) {
  const { main, acc, retail, dealer, rsiCross } = computeForceFlow(kline)

  const mainBars = main.map((v, i) => ({
    value: v,
    itemStyle: { color: i > 0 && v >= main[i - 1] ? UP : DOWN },
  }))
  const accBars = acc.map(v => ({ value: v, itemStyle: { color: UP } }))
  const crossPoints = dates
    .map((d, i) => ({ d, hit: rsiCross[i] }))
    .filter(x => x.hit)
    .map(x => ({ coord: [x.d, 80] as [string, number], value: '' }))

  return {
    grid: { left: 60, right: 20, top: '79.5%', height: '8.5%' },
    xAxis: {
      type: 'category' as const,
      data: dates,
      gridIndex: 5,
      boundaryGap: true,
      axisLabel: { show: false },
      axisPointer: { label: { show: false } },
    },
    yAxis: {
      scale: true,
      gridIndex: 5,
      splitNumber: 2,
      splitLine: { show: false },
      axisLabel: { show: false },
    },
    series: [
      {
        name: '主力进出',
        type: 'bar' as const,
        data: mainBars,
        xAxisIndex: 5,
        yAxisIndex: 5,
        barWidth: '55%',
        silent: true,
      },
      {
        name: '吸筹',
        type: 'bar' as const,
        data: accBars,
        xAxisIndex: 5,
        yAxisIndex: 5,
        barWidth: '55%',
        barGap: '-100%',
        silent: true,
      },
      {
        name: '散户线',
        type: 'line' as const,
        data: retail,
        xAxisIndex: 5,
        yAxisIndex: 5,
        showSymbol: false,
        silent: true,
        lineStyle: { width: 1.4, color: RETAIL },
        itemStyle: { color: RETAIL },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: RETAIL, width: 1, type: 'dashed' as const },
          data: [{ yAxis: STRONG_BOUNDARY }],
        },
        markPoint: {
          silent: true,
          symbol: 'triangle',
          symbolRotate: 180,
          symbolSize: 7,
          itemStyle: { color: DOWN },
          label: { show: false },
          data: crossPoints,
        },
      },
      {
        name: '庄家线',
        type: 'line' as const,
        data: dealer,
        xAxisIndex: 5,
        yAxisIndex: 5,
        showSymbol: false,
        silent: true,
        lineStyle: { width: 1.4, color: DEALER },
        itemStyle: { color: DEALER },
      },
    ],
  }
}
