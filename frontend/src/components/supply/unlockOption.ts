import type { EChartsOption } from 'echarts'
import type { TooltipComponentOption } from 'echarts/components'
import type { UnlockWeek } from '../../api/types'

const BOARDS = ['主板', '创业板', '科创板', '北交所'] as const

const COLORS: Record<string, string> = {
  主板: '#60a5fa',
  创业板: '#fbbf24',
  科创板: '#f472b6',
  北交所: '#34d399',
}

interface TooltipParam {
  seriesName: string
  value?: number | string
  axisValue: string
}

const unlockTooltip = (params: TooltipParam[]) => {
  const total = params.reduce((s, p) => s + Number(p.value ?? 0), 0)
  const rows = params
    .filter(p => Number(p.value ?? 0) > 0)
    .map(p => `${p.seriesName}：${Number(p.value).toFixed(1)} 亿`)
    .join('<br/>')
  return `<b>${params[0]?.axisValue} 当周</b><br/>${rows}<br/>合计：<b>${total.toFixed(1)} 亿</b>`
}

/** 未来逐周解禁供给(按板块堆叠)。 */
export function buildUnlockOption(weeks: UnlockWeek[]): EChartsOption | null {
  if (!weeks.length) return null
  const dates = weeks.map(w => w.week_start)
  const series = BOARDS.map(b => ({
    name: b,
    type: 'bar' as const,
    stack: 'unlock',
    barMaxWidth: 42,
    data: weeks.map(w => Number((w.by_board[b] ?? 0).toFixed(2))),
    itemStyle: { color: COLORS[b] },
  }))
  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#111827',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: unlockTooltip as unknown as TooltipComponentOption['formatter'],
    },
    legend: { data: [...BOARDS], textStyle: { color: '#9ca3af', fontSize: 11 }, top: 0 },
    grid: { left: 54, right: 16, top: 34, bottom: 26 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#6b7280', fontSize: 10 },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'value',
      name: '亿元',
      nameTextStyle: { color: '#6b7280', fontSize: 10 },
      axisLabel: { color: '#6b7280', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series,
  }
}
