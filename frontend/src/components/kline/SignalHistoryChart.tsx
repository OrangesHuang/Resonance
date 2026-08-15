import ReactECharts from 'echarts-for-react'
import * as echarts from 'echarts'
import type { DailySignal, ZoomWindow } from '../../api/types'

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

  const positionBars = points.map(p => {
    if (p?.price_position == null) return null
    const pp = p.price_position
    return {
      value: pp,
      itemStyle: { color: pp <= 40 ? '#22c55e' : pp >= 70 ? '#ef4444' : '#4b5563' },
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
      transitionDuration: 0,
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: (params: Array<{ axisValue: string; dataIndex: number }>) => {
        const p = params[0]
        const s = points[p.dataIndex]
        if (!s) return `${p.axisValue}<br/>无信号数据`
        const cp = s.composite_prob
        const cpDir = cp == null ? '' : cp >= 45 ? '吸筹' : cp <= 35 ? '出货' : '中性'
        const cpColor = cpDir === '吸筹' ? '#22c55e' : cpDir === '出货' ? '#ef4444' : '#f59e0b'
        const cpText = cp == null
          ? '-'
          : `${cp.toFixed(1)}%${cpDir ? `<span style="color:${cpColor}">（${cpDir}）</span>` : ''}`
        return `${p.axisValue}<br/>综合概率: <b>${cpText}</b><br/>量比: ${s.volume_ratio?.toFixed(2) ?? '-'}` +
          `<br/>价格位置: ${s.price_position?.toFixed(0) ?? '-'}%`
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
        { lte: 35, color: '#ef4444' },
        { gt: 35, lte: 45, color: '#f59e0b' },
        { gt: 45, color: '#22c55e' },
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
            { yAxis: 45, lineStyle: { color: '#22c55e', type: 'dashed' }, label: { formatter: '吸筹 45%', color: '#22c55e' } },
            { yAxis: 35, lineStyle: { color: '#ef4444', type: 'dashed' }, label: { formatter: '出货 35%', color: '#ef4444' } },
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
