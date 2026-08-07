import type { KlinePoint, DailySignal, TradePoint } from '../api/types'
import type { RangeStats } from './rangeStats'

const DIR_COLORS: Record<string, string> = {
  ACCUMULATE: '#22c55e',
  DISTRIBUTE: '#ef4444',
  NEUTRAL: '#374151',
}
const DIR_LABELS: Record<string, string> = {
  ACCUMULATE: '吸筹',
  DISTRIBUTE: '出货',
  NEUTRAL: '中性',
}

function fmtPct(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
}

function fmtFlow(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)} 亿份`
}

function rangeBlock(stats: RangeStats): string {
  const flow = stats.net_flow_yi
  const flowHtml = flow == null
    ? '区间净申赎：-'
    : `区间净申赎：<span style="color:${flow >= 0 ? '#22c55e' : '#ef4444'};font-weight:bold">${fmtFlow(flow)}</span>` +
      (stats.flow_days > 0 ? `（${stats.flow_days} 天）` : '')
  return `<div style="margin-top:6px;padding-top:5px;border-top:1px dashed #374151">` +
    `<b>区间 ${stats.start} ~ ${stats.end}</b><br/>` +
    `涨跌幅：<span style="color:${stats.change_pct >= 0 ? '#ef4444' : '#22c55e'};font-weight:bold">${fmtPct(stats.change_pct)}</span>` +
    `（首日收 ${stats.start_close.toFixed(3)} → 末日收 ${stats.end_close.toFixed(3)}）<br/>` +
    `${flowHtml}<br/>` +
    `最高 ${stats.high.toFixed(3)}(${stats.high_date}) · 最低 ${stats.low.toFixed(3)}(${stats.low_date})<br/>` +
    `振幅：${fmtPct(stats.amplitude_pct)} · 区间策略收益：${stats.range_return_pct == null ? '—' : fmtPct(stats.range_return_pct)}` +
    `</div>`
}

export function buildKlineTooltip(kline: KlinePoint[],
                                  sigByDate: Map<string, DailySignal>,
                                  tradesByDate: Map<string, TradePoint>,
                                  rangeStats?: RangeStats | null) {
  return (params: { dataIndex?: number }[]) => {
    const i = params[0]?.dataIndex
    const k = i != null ? kline[i] : undefined
    if (!k) return ''
    const s = sigByDate.get(k.date)
    const dir = s?.trade_direction ?? 'NEUTRAL'
    const dirColor = DIR_COLORS[dir] ?? '#9ca3af'
    const delta = s?.shares_delta_yi
    const prob = s?.composite_prob
    const trade = tradesByDate.get(k.date)
    const tradeHtml = trade
      ? `<br/><span style="color:${trade.action === 'BUY' ? '#22c55e' : '#ef4444'};font-weight:bold">` +
        `◆ ${trade.action === 'BUY' ? '买入' : '卖出'} @${trade.price} — ${trade.reason}</span>`
      : ''
    return `<div style="font-size:11px;line-height:1.8">` +
      `<b>${k.date}</b><br/>` +
      `开 ${k.open} · 收 ${k.close} · 高 ${k.high} · 低 ${k.low}<br/>` +
      `成交量：${k.volume.toLocaleString('zh-CN')}<br/>` +
      `份额净申赎：${delta != null ? `${delta > 0 ? '+' : ''}${delta.toFixed(2)} 亿份` : '-'}<br/>` +
      `综合概率：${prob != null ? `${prob.toFixed(1)}%` : '-'}<br/>` +
      `方向：<span style="color:${dirColor}"><b>${DIR_LABELS[dir] ?? dir}</b></span>` +
      tradeHtml +
      (rangeStats ? rangeBlock(rangeStats) : '') +
      `</div>`
  }
}
