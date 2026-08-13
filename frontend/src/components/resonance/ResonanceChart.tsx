import ReactECharts from 'echarts-for-react'
import type { ResonanceHistoryPoint } from '../../api/types'
import { windowToZoom, type DateWindow } from '../common/chartZoom'
import { useChartSync, RESONANCE_SYNC_GROUP } from '../../hooks/useChartSync'

const AXIS_LABEL = '#6b7280'
const SPLIT_LINE = '#1f2937'

interface TooltipParam {
  axisValue: string
  marker: string
  seriesName: string
  value: number | { value: number } | null
}

interface ClickParam {
  dataIndex?: number
}

export default function ResonanceChart({ history, selectedDate, onSelectDate, dateWindow }: {
  history: ResonanceHistoryPoint[]
  selectedDate?: string | null
  onSelectDate?: (date: string) => void
  dateWindow?: DateWindow | null
}) {
  const onChartReady = useChartSync(RESONANCE_SYNC_GROUP)

  if (history.length === 0) {
    return <div className="text-gray-500 text-center py-10">暂无数据</div>
  }

  const dates = history.map(h => h.date)
  const redData = history.map(h => h.red)
  const greenData = history.map(h => -h.green)
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
        const idx = dates.indexOf(date)
        if (idx < 0) return date
        const p = history[idx]
        return `${date}<br/>红灯 ${p.red} 盏<br/>绿灯 ${p.green} 盏`
      },
    },
    legend: {
      data: ['红灯数', '绿灯数'],
      textStyle: { color: AXIS_LABEL, fontSize: 10 },
      top: 0,
      right: 20,
    },
    grid: { left: 40, right: 20, top: 30, bottom: 60 },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: true,
      axisLabel: { color: AXIS_LABEL, fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      min: -5,
      max: 5,
      interval: 1,
      splitLine: { lineStyle: { color: SPLIT_LINE } },
      axisLabel: { color: AXIS_LABEL, formatter: (v: number) => `${Math.abs(v)}` },
    },
    series: [
      {
        name: '红灯数',
        type: 'bar',
        data: redData,
        stack: 'resonance',
        barMaxWidth: 10,
        itemStyle: { color: '#ef4444' },
      },
      {
        name: '绿灯数',
        type: 'bar',
        data: greenData,
        stack: 'resonance',
        barMaxWidth: 10,
        itemStyle: { color: '#22c55e' },
      },
    ],
    dataZoom: [
      { type: 'inside', start: zoom.start, end: zoom.end },
      {
        type: 'slider',
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
    click: (params: ClickParam) => {
      if (params.dataIndex == null) return
      const d = dates[params.dataIndex]
      if (d) onSelectDate?.(d)
    },
    // 缩放由 echarts.connect 原生组分发, 不再上报父级(避免多源状态更新)
  }

  return (
    <ReactECharts
      onChartReady={onChartReady}
      option={{
        ...option,
        series: option.series.map(s => ({
          ...s,
          cursor: 'pointer',
          ...(selectedDate
            ? {
                markLine: {
                  symbol: 'none',
                  silent: true,
                  animation: false,
                  data: [{ xAxis: selectedDate }],
                  lineStyle: { color: '#38bdf8', type: 'dashed', width: 1 },
                  label: { show: false },
                },
              }
            : {}),
        })),
      }}
      onEvents={onEvents}
      style={{ height: 260 }}
      notMerge
      lazyUpdate
    />
  )
}
