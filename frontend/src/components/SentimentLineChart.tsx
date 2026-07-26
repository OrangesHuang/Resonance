import ReactECharts from 'echarts-for-react'
import type { EChartsType } from 'echarts'
import { windowToZoom, zoomToWindow, type DateWindow } from './chartZoom'

interface LineSpec {
  name: string
  data: Array<number | null>
  color: string
  width?: number
}

interface BarSpec {
  name: string
  data: Array<number | null>
  colorFor?: (v: number) => string
}

interface Props {
  dates: string[]
  lines: LineSpec[]
  bars?: BarSpec
  height?: number | string
  yFormatter?: (v: number) => string
  barFormatter?: (v: number) => string
  lineTip?: (v: number) => string
  barTip?: (v: number) => string
  onReady?: (instance: EChartsType) => void
  selectedDate?: string | null
  onSelectDate?: (date: string) => void
  dateWindow?: DateWindow | null
  onZoomChange?: (w: DateWindow) => void
}

interface ClickParam {
  dataIndex?: number
}

interface DataZoomEvent {
  start?: number
  end?: number
  batch?: Array<{ start: number; end: number }>
}

interface TooltipParam {
  axisValue: string
  marker: string
  seriesName: string
  seriesType: string
  value: number | { value: number } | null
}

const AXIS_LABEL = '#6b7280'
const SPLIT_LINE = '#1f2937'

export default function SentimentLineChart({ dates, lines, bars, height = 320, yFormatter, barFormatter, lineTip, barTip, onReady, selectedDate, onSelectDate, dateWindow, onZoomChange }: Props) {
  if (dates.length === 0) {
    return <div className="text-gray-500 text-center py-10">暂无数据</div>
  }

  const hasBars = !!bars
  const hasLines = lines.length > 0
  const splitGrid = hasBars && hasLines
  const fmt = yFormatter ?? ((v: number) => `${v}`)
  const barFmt = barFormatter ?? ((v: number) => `${v.toFixed(0)}`)
  const tipFmt = lineTip ?? fmt

  const grids = splitGrid
    ? [
        { left: 60, right: 20, top: 20, height: '58%' },
        { left: 60, right: 20, top: '74%', height: '16%' },
      ]
    : [{ left: 60, right: 20, top: 20, bottom: 60 }]

  const barAxis = splitGrid ? 1 : 0

  const xAxes: Array<Record<string, unknown>> = [
    { type: 'category', data: dates, gridIndex: 0, boundaryGap: !hasLines, axisLabel: { color: AXIS_LABEL, fontSize: 10 } },
  ]
  const yAxes: Array<Record<string, unknown>> = [
    {
      type: 'value',
      gridIndex: 0,
      scale: true,
      splitLine: { lineStyle: { color: SPLIT_LINE } },
      axisLabel: { color: AXIS_LABEL, formatter: (v: number) => (hasLines ? fmt(v) : barFmt(v)) },
    },
  ]

  if (splitGrid) {
    xAxes.push({ type: 'category', data: dates, gridIndex: 1, boundaryGap: true, axisLabel: { show: false } })
    yAxes.push({
      type: 'value',
      gridIndex: 1,
      scale: true,
      splitNumber: 2,
      splitLine: { show: false },
      axisLabel: { color: AXIS_LABEL, fontSize: 9, formatter: (v: number) => barFmt(v) },
    })
  }

  const series: Array<Record<string, unknown>> = lines.map(l => ({
    name: l.name,
    type: 'line',
    data: l.data,
    xAxisIndex: 0,
    yAxisIndex: 0,
    showSymbol: false,
    smooth: false,
    connectNulls: false,
    lineStyle: { width: l.width ?? 1.5, color: l.color },
    itemStyle: { color: l.color },
  }))

  if (hasBars && bars) {
    const barData = bars.data.map(v => {
      if (v == null) return null
      const color = bars.colorFor ? bars.colorFor(v) : '#4b5563'
      return { value: v, itemStyle: { color } }
    })
    series.push({
      name: bars.name,
      type: 'bar',
      data: barData,
      xAxisIndex: barAxis,
      yAxisIndex: barAxis,
      barMaxWidth: splitGrid ? 6 : 10,
    })
  }

  const zoom = windowToZoom(dates, dateWindow ?? null)

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: (params: TooltipParam[]) => {
        const date = params[0]?.axisValue ?? ''
        const rows = params.map(p => {
          const raw = p.value
          const num = raw && typeof raw === 'object' ? raw.value : raw
          if (num == null || typeof num !== 'number') return `${p.marker}${p.seriesName}: -`
          const text = p.seriesType === 'bar'
            ? (barTip ? barTip(num) : `${num.toFixed(2)} 亿`)
            : tipFmt(num)
          return `${p.marker}${p.seriesName}: ${text}`
        })
        return `${date}<br/>${rows.join('<br/>')}`
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    legend: {
      data: lines.map(l => l.name),
      textStyle: { color: AXIS_LABEL, fontSize: 10 },
      top: 0,
      right: 20,
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    series,
    dataZoom: [
      { type: 'inside', xAxisIndex: splitGrid ? [0, 1] : [0], start: zoom.start, end: zoom.end },
      {
        type: 'slider',
        xAxisIndex: splitGrid ? [0, 1] : [0],
        start: zoom.start,
        end: zoom.end,
        bottom: 8,
        height: 18,
        borderColor: '#374151',
        backgroundColor: '#111827',
        fillerColor: 'rgba(75, 85, 99, 0.3)',
        handleStyle: { color: '#6b7280' },
        textStyle: { color: '#6b7280' },
      },
    ],
  }

  const onEvents: Record<string, (params: ClickParam & DataZoomEvent) => void> | undefined =
    onSelectDate || onZoomChange
      ? {
          click: params => {
            if (!onSelectDate || params.dataIndex == null) return
            const d = dates[params.dataIndex]
            if (d) onSelectDate(d)
          },
          datazoom: e => {
            if (!onZoomChange) return
            const z = e.batch ? e.batch[0] : e
            if (z.start == null || z.end == null) return
            const w = zoomToWindow(dates, z.start, z.end)
            if (w) onZoomChange(w)
          },
        }
      : undefined

  return (
    <ReactECharts
      option={{
        ...option,
        series: option.series.map((s, i) => ({
          ...s,
          ...(onSelectDate ? { cursor: 'pointer' } : {}),
          ...(selectedDate
            ? {
                markLine: {
                  symbol: 'none',
                  silent: true,
                  animation: false,
                  data: [{ xAxis: selectedDate }],
                  lineStyle: { color: '#38bdf8', type: 'dashed', width: 1 },
                  label: { show: i === 0, position: 'start', color: '#38bdf8', fontSize: 9 },
                },
              }
            : {}),
        })),
      }}
      onEvents={onEvents}
      style={{ height }}
      notMerge
      lazyUpdate
      onChartReady={onReady}
    />
  )
}
