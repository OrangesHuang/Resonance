import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { KlinePoint, TradePoint } from '../api/types'

interface TooltipParam {
  dataIndex?: number
}

export default function CompareKline({ kline, trades, height = 320 }: {
  kline: KlinePoint[]
  trades: TradePoint[]
  height?: number
}) {
  const option = useMemo(() => {
    if (kline.length === 0) return null
    const dates = kline.map(k => k.date)
    const ohlc = kline.map(k => [k.open, k.close, k.low, k.high])
    const volumes = kline.map(k => k.volume)
    const ma20 = kline.map((_, i) => {
      const lo = Math.max(0, i - 19)
      const win = kline.slice(lo, i + 1)
      return Number((win.reduce((s, k) => s + k.close, 0) / win.length).toFixed(3))
    })

    const klineByDate = new Map(kline.map(k => [k.date, k]))
    const tradesByDate = new Map(trades.map(t => [t.date, t]))
    // 标记始终定义为对象(数据为空数组即清除), 避免 merge 残留
    const markPoint = {
      clip: false,
      data: trades
        .filter(t => klineByDate.has(t.date))
        .map(t => {
          const k = klineByDate.get(t.date)!
          const isBuy = t.action === 'BUY'
          return {
            coord: [t.date, isBuy ? k.low * 0.995 : k.high * 1.005],
            value: isBuy ? 'B' : 'S',
            symbol: isBuy ? 'triangle' : 'pin',
            symbolSize: isBuy ? 18 : 20,
            symbolRotate: isBuy ? 0 : 180,
            itemStyle: { color: isBuy ? '#15803d' : '#ef4444' },
            label: { show: true, formatter: isBuy ? '买' : '卖', fontSize: 10, color: '#fff', offset: [0, isBuy ? 5 : -5] as [number, number] },
            _reason: `${t.date} ${isBuy ? '买入' : '卖出'} @${t.price}\n${t.reason}`,
          }
        }),
      tooltip: {
        formatter: (p: { data?: { _reason?: string } }) =>
          (p.data?._reason ?? '').replace('\n', '<br/>'),
      },
    }

    const tooltipFormatter = (params: TooltipParam[]) => {
      const i = params[0]?.dataIndex
      const k = i != null ? kline[i] : undefined
      if (!k) return ''
      const m = tradesByDate.get(k.date)
      const tradeHtml = m
        ? `<br/><span style="color:${m.action === 'BUY' ? '#22c55e' : '#ef4444'};font-weight:bold">` +
          `◆ ${m.action === 'BUY' ? '买入' : '卖出'} @${m.price} — ${m.reason}</span>`
        : ''
      return `<div style="font-size:11px;line-height:1.8">` +
        `<b>${k.date}</b><br/>` +
        `开 ${k.open} · 收 ${k.close} · 高 ${k.high} · 低 ${k.low}<br/>` +
        `成交量：${k.volume.toLocaleString('zh-CN')}` +
        tradeHtml +
        `</div>`
    }

    return {
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
      grid: [
        { left: 55, right: 16, top: 12, height: '66%' },
        { left: 55, right: 16, top: '82%', height: '11%' },
      ],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0, boundaryGap: true, axisLabel: { color: '#6b7280', fontSize: 10 } },
        { type: 'category', data: dates, gridIndex: 1, boundaryGap: true, axisLabel: { show: false } },
      ],
      yAxis: [
        { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: '#1f2937' } }, axisLabel: { color: '#6b7280' } },
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
          markPoint,
        },
        {
          name: 'MA20',
          type: 'line',
          data: ma20,
          xAxisIndex: 0,
          yAxisIndex: 0,
          showSymbol: false,
          lineStyle: { width: 1, color: '#38bdf8' },
          itemStyle: { color: '#38bdf8' },
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
        { type: 'inside', xAxisIndex: [0, 1] },
        {
          type: 'slider',
          xAxisIndex: [0, 1],
          top: '95%',
          height: 14,
          borderColor: '#374151',
          backgroundColor: '#111827',
          fillerColor: 'rgba(75, 118, 99, 0.3)',
          handleStyle: { color: '#6b7280' },
          textStyle: { color: '#6b7280' },
        },
      ],
    }
  }, [kline, trades])

  if (option === null) {
    return <div className="text-gray-500 text-center py-8 text-sm">暂无K线数据</div>
  }

  return <ReactECharts option={option} style={{ height }} lazyUpdate />
}
