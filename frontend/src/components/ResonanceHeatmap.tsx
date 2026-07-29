import ReactECharts from 'echarts-for-react'
import type { ResonanceOverview, LightState } from '../api/types'
import { windowToZoom, zoomToWindow, type DateWindow } from './chartZoom'

const AXIS_LABEL = '#6b7280'

const STATE_VALUE: Record<LightState, number> = { red: 2, green: 1, gray: 0 }
const VALUE_LABEL: Record<number, string> = { 2: '红灯', 1: '绿灯', 0: '中性' }

interface HeatmapTooltipParam {
  value: [number, number, number]
}

interface DataZoomEvent {
  start?: number
  end?: number
  batch?: Array<{ start: number; end: number }>
}

export default function ResonanceHeatmap({ data, selectedDate, onSelect, dateWindow, onZoomChange }: {
  data: ResonanceOverview
  selectedDate?: string | null
  onSelect?: (date: string, indicatorKey: string) => void
  dateWindow?: DateWindow | null
  onZoomChange?: (w: DateWindow) => void
}) {
  const history = data.history
  const keys = data.indicators.map(i => i.key)
  const names = data.indicators.map(i => i.name)

  if (history.length === 0 || keys.length === 0) {
    return <div className="text-gray-500 text-center py-10">暂无数据</div>
  }

  const dates = history.map(h => h.date)
  const zoom = windowToZoom(dates, dateWindow ?? null)
  type HeatCell = [number, number, number] | {
    value: [number, number, number]
    itemStyle: { borderColor: string; borderWidth: number; shadowBlur: number; shadowColor: string }
  }
  const heatData: HeatCell[] = []
  const selectedCells: HeatCell[] = []
  history.forEach((h, x) => {
    const isSel = selectedDate != null && h.date === selectedDate
    keys.forEach((key, y) => {
      const st: LightState = h.states[key] ?? 'gray'
      const v: [number, number, number] = [x, y, STATE_VALUE[st]]
      if (isSel) {
        selectedCells.push({ value: v, itemStyle: { borderColor: '#38bdf8', borderWidth: 2, shadowBlur: 10, shadowColor: 'rgba(56, 189, 248, 0.9)' } })
      } else {
        heatData.push(v)
      }
    })
  })
  heatData.push(...selectedCells)

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      backgroundColor: '#111827',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: (param: HeatmapTooltipParam) => {
        const [x, y, v] = param.value
        return `${dates[x]}<br/>${names[y]}：${VALUE_LABEL[v] ?? '中性'}`
      },
    },
    grid: { left: 80, right: 20, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: true,
      splitArea: { show: false },
      axisLabel: { color: AXIS_LABEL, fontSize: 10 },
    },
    yAxis: {
      type: 'category',
      data: names,
      inverse: true,
      splitArea: { show: false },
      axisLabel: { color: AXIS_LABEL, fontSize: 11 },
    },
    visualMap: {
      type: 'piecewise',
      dimension: 2,
      pieces: [
        { value: 2, label: '红灯', color: '#ef4444' },
        { value: 1, label: '绿灯', color: '#22c55e' },
        { value: 0, label: '中性', color: '#374151' },
      ],
      orient: 'horizontal',
      left: 80,
      top: 5,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { color: AXIS_LABEL, fontSize: 10 },
    },
    series: [
      {
        name: '共振状态',
        type: 'heatmap',
        data: heatData,
        itemStyle: { borderColor: '#0a0f1a', borderWidth: 1 },
        emphasis: { itemStyle: { borderColor: '#e5e7eb', borderWidth: 1 } },
      },
      ...(selectedDate != null && dates.includes(selectedDate) ? [{
        name: '选中高亮',
        type: 'custom',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: keys.map((_, y) => [dates.indexOf(selectedDate), y]),
        silent: true,
        z: 10,
        renderItem: (_params: unknown, api: { value: (idx: number) => number; coord: (v: [number, number]) => [number, number]; getWidth: () => number; getHeight: () => number }) => {
          const xIdx = api.value(0)
          const yIdx = api.value(1)
          const [cx, cy] = api.coord([xIdx, yIdx])
          const colWidth = api.getWidth() / (dates.length * ((zoom.end - zoom.start) / 100))
          const cellW = Math.max(colWidth, 10)
          const rowH = keys.length > 1
            ? Math.abs(api.coord([0, 1])[1] - api.coord([0, 0])[1])
            : api.getHeight()
          const st: LightState = history[xIdx]?.states[keys[yIdx]] ?? 'gray'
          const color = st === 'red' ? '#ef4444' : st === 'green' ? '#22c55e' : '#374151'
          return {
            type: 'rect',
            shape: { x: cx - cellW / 2, y: cy - rowH / 2, width: cellW, height: rowH - 1 },
            style: { fill: color, stroke: '#38bdf8', lineWidth: 1.5 },
          }
        },
      }] : []),
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, start: zoom.start, end: zoom.end },
      {
        type: 'slider',
        xAxisIndex: 0,
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

  const onEvents = {
    click: (params: HeatmapTooltipParam) => {
      const [x, y] = params.value
      const date = dates[x]
      const key = keys[y]
      if (date && key) onSelect?.(date, key)
    },
    datazoom: (e: DataZoomEvent) => {
      if (!onZoomChange) return
      const z = e.batch ? e.batch[0] : e
      if (z.start == null || z.end == null) return
      const w = zoomToWindow(dates, z.start, z.end)
      if (w) onZoomChange(w)
    },
  }

  return (
    <ReactECharts
      option={{
        ...option,
        series: option.series.map(s => ({ ...s, cursor: 'pointer' })),
      }}
      onEvents={onEvents}
      style={{ height: 260 }}
      notMerge
      lazyUpdate
    />
  )
}
