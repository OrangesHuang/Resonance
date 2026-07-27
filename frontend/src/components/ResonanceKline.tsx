import ReactECharts from 'echarts-for-react'
import type { KlinePoint, ResonanceHistoryPoint, DailySignal, TradePoint } from '../api/types'
import { windowToZoom, zoomToWindow, DEFAULT_VISIBLE_BARS, type DateWindow } from './chartZoom'

const AXIS_LABEL = '#6b7280'
const DANGER_BAND = 'rgba(239, 68, 68, 0.08)'
const CHANCE_BAND = 'rgba(34, 197, 94, 0.08)'
const UP_COLOR = '#ef4444'
const DOWN_COLOR = '#22c55e'

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

interface ClickParam {
  dataIndex?: number
  componentType?: string
  data?: { coord?: [string, number] }
}

interface ZoomEvent {
  start?: number
  end?: number
  batch?: Array<{ start: number; end: number }>
}

interface TooltipParam {
  dataIndex?: number
}

export default function ResonanceKline({ kline, history, signals, trades, selectedDate, onSelectDate, dateWindow, onZoomChange }: {
  kline: KlinePoint[]
  history: ResonanceHistoryPoint[]
  signals: DailySignal[]
  trades: TradePoint[]
  selectedDate: string | null
  onSelectDate: (date: string) => void
  dateWindow: DateWindow | null
  onZoomChange: (w: DateWindow) => void
}) {
  if (kline.length === 0) {
    return <div className="text-gray-500 text-center py-10">暂无K线数据</div>
  }

  const dates = kline.map(k => k.date)
  const ohlc = kline.map(k => [k.open, k.close, k.low, k.high])
  const volumes = kline.map(k => k.volume)

  const sigByDate = new Map<string, DailySignal>()
  for (const s of signals) sigByDate.set(s.date, s)
  const flowData = dates.map(d => {
    const v = sigByDate.get(d)?.shares_delta_yi
    if (v == null) return { value: null, itemStyle: { color: '#374151' } }
    return { value: v, itemStyle: { color: v >= 0 ? DOWN_COLOR : UP_COLOR } }
  })
  const probData = dates.map(d => sigByDate.get(d)?.composite_prob ?? null)
  const dirData = dates.map(d => {
    const dir = sigByDate.get(d)?.trade_direction ?? 'NEUTRAL'
    return { value: 1, itemStyle: { color: DIR_COLORS[dir] ?? '#374151' } }
  })

  const { start: zoomStart, end: zoomEnd } = windowToZoom(dates, dateWindow, DEFAULT_VISIBLE_BARS)

  const bands = history
    .filter(h => h.red >= 3 || h.green >= 3)
    .map(h => [
      { xAxis: h.date, itemStyle: { color: h.red >= 3 ? DANGER_BAND : CHANCE_BAND } },
      { xAxis: h.date },
    ])

  const klineByDate = new Map(kline.map(k => [k.date, k]))
  const tradeMarks = trades
    .filter(t => klineByDate.has(t.date))
    .map(t => {
      const k = klineByDate.get(t.date)!
      const isBuy = t.action === 'BUY'
      return {
        coord: [t.date, isBuy ? k.low * 0.995 : k.high * 1.005],
        value: isBuy ? 'B' : 'S',
        symbol: isBuy ? 'triangle' : 'pin',
        symbolSize: isBuy ? 22 : 24,
        symbolRotate: isBuy ? 0 : 180,
        itemStyle: { color: isBuy ? '#15803d' : '#ef4444' },
        label: { show: true, formatter: isBuy ? '买' : '卖', fontSize: 11, color: '#fff', offset: [0, isBuy ? 5 : -5] as [number, number] },
        _reason: `${t.date} ${isBuy ? '买入' : '卖出'} @${t.price}\n${t.reason}`,
      }
    })
  const markPoint = tradeMarks.length > 0 ? {
    data: tradeMarks,
    tooltip: {
      formatter: (p: { data?: { _reason?: string } }) =>
        (p.data?._reason ?? '').replace('\n', '<br/>'),
    },
  } : undefined

  const showMarkLine = selectedDate !== null && dates.includes(selectedDate)
  const markLine = showMarkLine ? {
    silent: true,
    symbol: 'none',
    lineStyle: { color: '#38bdf8', type: 'dashed' as const, width: 1 },
    label: { show: false },
    data: [{ xAxis: selectedDate }],
  } : undefined
  const markLineTop = showMarkLine ? {
    ...markLine,
    label: { show: true, formatter: selectedDate ?? '', color: '#38bdf8', fontSize: 10, position: 'insideEndTop' },
  } : undefined
  const probMarkLine = {
    silent: true,
    symbol: 'none',
    label: { fontSize: 9 },
    data: [
      { yAxis: 70, lineStyle: { color: '#ef4444', type: 'dashed' }, label: { formatter: 'HIGH 70%', color: '#ef4444' } },
      { yAxis: 50, lineStyle: { color: '#f59e0b', type: 'dashed' }, label: { formatter: 'MID 50%', color: '#f59e0b' } },
      ...(showMarkLine
        ? [{ xAxis: selectedDate, lineStyle: { color: '#38bdf8', type: 'dashed' }, label: { show: false } }]
        : []),
    ],
  }

  const onEvents = {
    click: (params: ClickParam) => {
      if (params.componentType === 'markPoint' && params.data?.coord) {
        onSelectDate(params.data.coord[0])
        return
      }
      const d = params.dataIndex != null ? dates[params.dataIndex] : undefined
      if (d) onSelectDate(d)
    },
    datazoom: (e: ZoomEvent) => {
      const z = e.batch ? e.batch[0] : e
      if (z.start != null && z.end != null) {
        const w = zoomToWindow(dates, z.start, z.end)
        if (w) onZoomChange(w)
      }
    },
  }

  const tradeByDate = new Map(trades.map(t => [t.date, t]))
  const tooltipFormatter = (params: TooltipParam[]) => {
    const i = params[0]?.dataIndex
    const k = i != null ? kline[i] : undefined
    if (!k) return ''
    const s = sigByDate.get(k.date)
    const dir = s?.trade_direction ?? 'NEUTRAL'
    const dirColor = DIR_COLORS[dir] ?? '#9ca3af'
    const delta = s?.shares_delta_yi
    const prob = s?.composite_prob
    const trade = tradeByDate.get(k.date)
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
      `</div>`
  }

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#111827',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: tooltipFormatter,
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    visualMap: {
      show: false,
      seriesIndex: 3,
      dimension: 1,
      pieces: [
        { lte: 50, color: '#22c55e' },
        { gt: 50, lte: 70, color: '#f59e0b' },
        { gt: 70, color: '#ef4444' },
      ],
      outOfRange: { color: '#6b7280' },
    },
    grid: [
      { left: 60, right: 20, top: 20, height: '34%' },
      { left: 60, right: 20, top: '52%', height: '7%' },
      { left: 60, right: 20, top: '62%', height: '7%' },
      { left: 60, right: 20, top: '72%', height: '9%' },
      { left: 60, right: 20, top: '84%', height: '4%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, boundaryGap: true, axisLabel: { color: AXIS_LABEL, fontSize: 10 } },
      { type: 'category', data: dates, gridIndex: 1, boundaryGap: true, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 2, boundaryGap: true, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 3, boundaryGap: false, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 4, boundaryGap: true, axisLabel: { show: false } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: '#1f2937' } }, axisLabel: { color: AXIS_LABEL } },
      { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false } },
      { scale: true, gridIndex: 2, splitLine: { show: false }, axisLabel: { color: AXIS_LABEL, fontSize: 9 } },
      { min: 0, max: 100, gridIndex: 3, splitNumber: 2, splitLine: { show: false }, axisLabel: { color: AXIS_LABEL, fontSize: 9, formatter: '{value}%' } },
      { min: 0, max: 1, gridIndex: 4, splitLine: { show: false }, axisLabel: { show: false } },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: UP_COLOR,
          color0: DOWN_COLOR,
          borderColor: UP_COLOR,
          borderColor0: DOWN_COLOR,
        },
        markArea: bands.length > 0 ? { silent: true, data: bands } : undefined,
        markLine: markLineTop,
        markPoint,
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: { color: '#4b5563' },
        markLine,
      },
      {
        name: '份额净申赎(亿份)',
        type: 'bar',
        data: flowData,
        xAxisIndex: 2,
        yAxisIndex: 2,
        markLine,
      },
      {
        name: '综合概率',
        type: 'line',
        data: probData,
        xAxisIndex: 3,
        yAxisIndex: 3,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.5 },
        areaStyle: { opacity: 0.08 },
        markLine: probMarkLine,
      },
      {
        name: '交易方向',
        type: 'bar',
        data: dirData,
        xAxisIndex: 4,
        yAxisIndex: 4,
        barWidth: '60%',
        markLine,
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2, 3, 4], start: zoomStart, end: zoomEnd },
      {
        type: 'slider',
        xAxisIndex: [0, 1, 2, 3, 4],
        start: zoomStart,
        end: zoomEnd,
        top: '92%',
        height: 16,
        borderColor: '#374151',
        backgroundColor: '#111827',
        fillerColor: 'rgba(75, 85, 99, 0.3)',
        handleStyle: { color: '#6b7280' },
        textStyle: { color: '#6b7280' },
      },
    ],
  }

  return (
    <ReactECharts
      option={option}
      style={{ height: 620, cursor: 'pointer' }}
      notMerge
      lazyUpdate
      onEvents={onEvents}
    />
  )
}
