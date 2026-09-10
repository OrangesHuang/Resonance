import type { KlinePoint } from '../../api/types'

/**
 * 主 K 线面板(gridIndex 0)上的长周期价格均线叠加: EMA120 / EMA350。
 *
 * 认知:
 *  - EMA 是【价格量纲】的均线, 与 MA250 同一属性, 因此可以直接共享价格轴
 *    (yAxisIndex: 0) —— 放大/缩小都不会跳位置。这一点与 MACD 那种"以 0 为中心
 *    的振荡指标"有本质区别: 振荡指标若挂一根独立轴叠在价格面板上, 会随可见窗口
 *    自动缩放(scale:true), 换个缩放级别就被画到面板的另一处(历史 bug: 缩小时
 *    线从 K 线上方"跑"到下方)。
 *  - EMA120 上穿 EMA350 = 长周期动量转多, 下穿 = 转空, 可作牛熊大循环的分界参考。
 *  - 预热期样本不足时输出 null(EMA350 需约 350 根才稳定), 避免开头画出误导性曲线。
 */

const EMA_FAST_SPAN = 120
const EMA_SLOW_SPAN = 350

export const EMA_FAST_COLOR = '#22d3ee' // EMA120 青色
export const EMA_SLOW_COLOR = '#818cf8' // EMA350 靛蓝

function emaSeries(closes: number[], span: number): (number | null)[] {
  const k = 2 / (span + 1)
  const out: (number | null)[] = []
  let prev = 0
  for (let i = 0; i < closes.length; i++) {
    prev = i === 0 ? closes[0] : closes[i] * k + prev * (1 - k)
    // 样本不足 span 根 → 不画(预热期)
    out.push(i >= span - 1 ? Math.round(prev * 10000) / 10000 : null)
  }
  return out
}

/** 返回主图叠加所需的 series(挂在价格轴 yAxisIndex:0 上)。 */
export function buildEmaOverlay(kline: KlinePoint[]) {
  const closes = kline.map(k => k.close)
  const base = {
    type: 'line' as const,
    xAxisIndex: 0,
    yAxisIndex: 0,
    showSymbol: false,
    connectNulls: false,
    silent: true,
    lineStyle: { width: 1.2 },
  }
  return {
    series: [
      { ...base, name: `EMA${EMA_FAST_SPAN}`, data: emaSeries(closes, EMA_FAST_SPAN), lineStyle: { ...base.lineStyle, color: EMA_FAST_COLOR } },
      { ...base, name: `EMA${EMA_SLOW_SPAN}`, data: emaSeries(closes, EMA_SLOW_SPAN), lineStyle: { ...base.lineStyle, color: EMA_SLOW_COLOR } },
    ],
  }
}
