import ReactECharts from 'echarts-for-react'
import * as echarts from 'echarts'
import type { DailySignal, ZoomWindow } from '../api/types'

interface Props {
  dates: string[]
  points: Array<DailySignal | null>
  groupId: string
  height?: number | string
  zoom: ZoomWindow
  onReady?: (inst: echarts.ECharts) => void
}

export default function SignalHistoryChart({ dates, points, groupId, height = 420, zoom, onReady }: Props) {
  if (dates.length === 0) {
    return <div className="text-gray-500 text-center py-10">暂无信号数据</div>
  }

  const probs = points.map(p => p?.composite_prob ?? null)

  const DIR_COLORS: Record<string, string> = {
    ACCUMULATE: '#ef4444',
    DISTRIBUTE: '#06b6d4',
    NEUTRAL: '#374151',
  }
  const DIR_LABELS: Record<string, string> = {
    ACCUMULATE: '吸筹',
    DISTRIBUTE: '出货',
    NEUTRAL: '中性',
  }

  const positionBars = points.map(p => {
    if (p?.price_position == null) return null
    const dir = p.trade_direction ?? 'NEUTRAL'
    return {
      value: p.price_position,
      itemStyle: { color: DIR_COLORS[dir] || '#374151' },
    }
  })

  const onChartReady = (inst: echarts.ECharts) => {
    inst.group = groupId
    echarts.connect(groupId)
    onReady?.(inst)
  }

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: (params: Array<{ axisValue: string; dataIndex: number }>) => {
        const p = params[0]
        const s = points[p.dataIndex]
        if (!s) return `${p.axisValue}<br/>无信号数据`
        const dir = s.trade_direction ?? 'NEUTRAL'
        const dirColor = DIR_COLORS[dir] || '#9ca3af'
        return `${p.axisValue}<br/>综合概率: <b>${s.composite_prob?.toFixed(1) ?? '-'}%</b><br/>信号: ${s.signal_level ?? '-'}<br/>量比: ${s.volume_ratio?.toFixed(2) ?? '-'}` +
          `<br/>价格位置: ${s.price_position?.toFixed(0) ?? '-'}%` +
          `<br/>方向: <span style="color:${dirColor}"><b>${DIR_LABELS[dir] || dir}</b></span>`
      },
    },
    grid: [
      { left: 50, right: 20, top: 30, height: '52%' },
      { left: 50, right: 20, top: '70%', height: '14%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        axisLabel: { show: false },
        boundaryGap: false,
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        axisLabel: { color: '#6b7280', fontSize: 10 },
        boundaryGap: true,
      },
    ],
    yAxis: [
      {
        type: 'value',
        min: 0,
        max: 100,
        splitLine: { lineStyle: { color: '#1f2937' } },
        axisLabel: { color: '#6b7280', formatter: '{value}%' },
      },
      {
        type: 'value',
        gridIndex: 1,
        min: 0,
        max: 100,
        splitNumber: 2,
        splitLine: { show: false },
        axisLabel: { color: '#6b7280', fontSize: 9, formatter: '{value}' },
      },
    ],
    visualMap: {
      show: false,
      seriesIndex: 0,
      dimension: 1,
      pieces: [
        { lte: 50, color: '#22c55e' },
        { gt: 50, lte: 70, color: '#f59e0b' },
        { gt: 70, color: '#ef4444' },
      ],
      outOfRange: { color: '#6b7280' },
    },
    series: [
      {
        name: '综合概率',
        type: 'line',
        data: probs,
        showSymbol: false,
        smooth: false,
        connectNulls: false,
        lineStyle: { width: 1.5 },
        areaStyle: { opacity: 0.08 },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { fontSize: 10 },
          data: [
            { yAxis: 70, lineStyle: { color: '#ef4444', type: 'dashed' }, label: { formatter: 'HIGH 70%', color: '#ef4444' } },
            { yAxis: 50, lineStyle: { color: '#f59e0b', type: 'dashed' }, label: { formatter: 'MID 50%', color: '#f59e0b' } },
          ],
        },
      },
      {
        name: '价格位置',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: positionBars,
        barMaxWidth: 4,
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: zoom.start, end: zoom.end },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        start: zoom.start,
        end: zoom.end,
        top: '90%',
        height: 18,
        borderColor: '#374151',
        backgroundColor: '#111827',
        fillerColor: 'rgba(75, 85, 99, 0.3)',
        handleStyle: { color: '#6b7280' },
        textStyle: { color: '#6b7280' },
      },
    ],
  }

  return <ReactECharts option={option} style={{ height }} notMerge lazyUpdate onChartReady={onChartReady} />
}
