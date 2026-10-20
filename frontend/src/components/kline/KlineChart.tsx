import ReactECharts from 'echarts-for-react'
import * as echarts from 'echarts'
import type { DailySignal, KlinePoint, ZoomWindow } from '../../api/types'
import {
  fmtPrice, fmtSignedPct, pctColor, priceAxisLabel, pricePointerLabel,
} from '../../utils/format'

interface Props {
  kline: KlinePoint[]
  signals?: DailySignal[]
  groupId: string
  height?: number | string
  zoom: ZoomWindow
  onReady?: (inst: echarts.ECharts) => void
}

function detailTooltip(k: KlinePoint, chg: number | null | undefined): string {
  const col = pctColor(chg)
  const chgSpan = `<span style="color:${col};font-weight:bold">${fmtSignedPct(chg)}</span>`
  const head = chg == null ? `<b>${k.date}</b>` : `<b>${k.date}</b> · ${chgSpan}`
  const o = fmtPrice(k.open)
  const c = fmtPrice(k.close)
  const h = fmtPrice(k.high)
  const l = fmtPrice(k.low)
  const vol = k.volume.toLocaleString('zh-CN')
  return `<div style="font-size:11px;line-height:1.8">` +
    `${head}<br/>` +
    `开 ${o} · 收 ${c} · 高 ${h} · 低 ${l}<br/>` +
    `成交量：${vol}</div>`
}

export default function KlineChart({
  kline, signals = [], groupId, height = 520, zoom, onReady,
}: Props) {
  if (kline.length === 0) {
    return <div className="text-gray-500 text-center py-10">暂无K线数据</div>
  }

  const dates = kline.map(k => k.date)
  const ohlc = kline.map(k => [k.open, k.close, k.low, k.high])
  const volumes = kline.map(k => k.volume)
  const chgByDate = new Map(signals.map(s => [s.date, s.change_pct]))

  const onChartReady = (inst: echarts.ECharts) => {
    inst.group = groupId
    echarts.connect(groupId)
    onReady?.(inst)
  }

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      transitionDuration: 0,
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#111827',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: (params: { dataIndex?: number }[]) => {
        const i = params?.[0]?.dataIndex
        const k = i == null ? undefined : kline[i]
        return k ? detailTooltip(k, chgByDate.get(k.date)) : ''
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 60, right: 20, top: 20, height: '58%' },
      { left: 60, right: 20, top: '76%', height: '14%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false }, axisPointer: { label: { show: false } }, boundaryGap: true },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false }, axisPointer: { label: { show: false } }, boundaryGap: true },
    ],
    yAxis: [
      {
        scale: true,
        gridIndex: 0,
        splitLine: { lineStyle: { color: '#1f2937' } },
        axisLabel: priceAxisLabel('#6b7280'),
        axisPointer: pricePointerLabel,
      },
      { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false } },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#ef4444',
          color0: '#22c55e',
          borderColor: '#ef4444',
          borderColor0: '#22c55e',
        },
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: { color: '#4b5563' },
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: zoom.start, end: zoom.end, preventDefaultMouseMove: true },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        start: zoom.start,
        end: zoom.end,
        top: '93%',
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
