import { useMemo, useRef, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import useIsMobile from '../hooks/useIsMobile'
import { TradePopup, placePopup } from './TradePopups'
import type { PopupState } from './TradePopups'
import type { PortfolioBacktestResponse } from '../api/types'

const KIND_CLR: Record<string, string> = {
  BUY: '#22c55e', TOPUP: '#38bdf8', SWITCH: '#f59e0b', SELL: '#ef4444', SKIP: '#9ca3af',
}
const KIND_ZH: Record<string, string> = {
  BUY: '买入', TOPUP: '加仓', SWITCH: '转仓', SELL: '卖出', SKIP: '信号跳过',
}
const ETF_COLORS = ['#a78bfa', '#2dd4bf', '#f472b6', '#facc15',
                    '#fb923c', '#34d399', '#60a5fa', '#c084fc', '#94a3b8']

function fmtWan(v: number): string {
  return `${(v / 10000).toFixed(1)} 万`
}

export default function PortfolioChart({ data, displayRowsByDate }: {
  data: PortfolioBacktestResponse
  displayRowsByDate: Map<string, { date: string; kind: string; kind_label: string; name: string; code: string; signal_date: string; units: number; price: number; amount: number }[]>
}) {
  const isMobile = useIsMobile()
  const [popups, setPopups] = useState<PopupState[]>([])
  const chartRef = useRef<ReactECharts | null>(null)
  const chartWrapRef = useRef<HTMLDivElement | null>(null)

  const option = useMemo(() => {
    if (!data || data.curve.length === 0) return null
    const dates = data.curve.map(c => c.date)
    const nav = data.curve.map(c => c.nav_per_share)
    const pos = data.curve.map(c => c.position_pct)

    // 空仓段(仓位=0 的连续交易日区间), 供 tooltip 展示起止与持续天数
    const emptySegs: { start: string; end: string; days: number }[] = []
    let seg: { start: string; days: number } | null = null
    let lastDate = ''
    for (const c of data.curve) {
      if (c.position_pct === 0) {
        if (!seg) seg = { start: c.date, days: 0 }
        seg.days += 1
      } else if (seg) {
        emptySegs.push({ start: seg.start, end: lastDate, days: seg.days })
        seg = null
      }
      lastDate = c.date
    }
    if (seg) emptySegs.push({ start: seg.start, end: lastDate, days: seg.days })

    // 主图: 组合操作发光圆点(点击弹出交易记录)
    const markers: { coord: [string, number]; itemStyle: { color: string; shadowBlur: number; shadowColor: string } }[] = []
    for (const [date, rows] of displayRowsByDate) {
      const idx = dates.indexOf(date)
      if (idx < 0) continue
      const main = rows[0]
      const posVal = data.curve[idx]?.position_pct ?? 0
      const clr = KIND_CLR[main.kind] ?? '#9ca3af'
      markers.push({
        coord: [date, posVal],
        itemStyle: { color: clr, shadowBlur: 14, shadowColor: clr },
      })
    }

    const series: object[] = [
      {
        name: '每份净值(元)',
        type: 'line',
        data: nav,
        showSymbol: false,
        lineStyle: { width: 1.8, color: '#22c55e' },
        itemStyle: { color: '#22c55e' },
        areaStyle: { color: 'rgba(34, 197, 94, 0.08)' },
      },
      {
        name: '仓位%',
        type: 'line',
        yAxisIndex: 1,
        data: pos,
        showSymbol: false,
        lineStyle: { width: 1, color: '#38bdf8', type: 'dashed' as const },
        itemStyle: { color: '#38bdf8' },
        markPoint: {
          symbol: 'circle',
          symbolSize: 10,
          symbolOffset: [0, -8],
          data: markers,
        },
      },
    ]

    // 副图: 各 ETF 归一化净值线 + B/S 买卖点(grid 1) 与 份额净申赎量柱(grid 2)
    data.etf_series.forEach((etf, i) => {
      const color = ETF_COLORS[i % ETF_COLORS.length]
      series.push({
        name: etf.name,
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 2,
        data: etf.nav,
        showSymbol: false,
        lineStyle: { width: 1.2, color },
        itemStyle: { color },
      })
      series.push({
        name: `${etf.name}净申赎`,
        type: 'bar',
        xAxisIndex: 2,
        yAxisIndex: 3,
        data: etf.delta.map(v => v == null ? null : {
          value: v,
          itemStyle: { color: v >= 0 ? '#ef4444' : '#22c55e' },
        }),
        barWidth: '55%',
      })
      const marks: { coord: [string, number]; value: string; itemStyle: { color: string }; label: { fontSize: number; fontWeight: string; color: string } }[] = []
      for (const t of etf.trades) {
        const idx = dates.indexOf(t.date)
        if (idx < 0) continue
        const v = etf.nav[idx]
        if (v == null) continue
        const buy = t.action === 'BUY'
        marks.push({
          coord: [t.date, v],
          value: buy ? 'B' : 'S',
          itemStyle: { color: buy ? '#22c55e' : '#ef4444' },
          label: { fontSize: 9, fontWeight: 'bold', color: '#fff' },
        })
      }
      const navSeries = series[series.length - 2] as { markPoint?: object }
      navSeries.markPoint = { symbol: 'pin', symbolSize: 24, data: marks }
    })

    const axisBase = {
      axisLabel: { color: '#6b7280', fontSize: 10 },
      axisLine: { lineStyle: { color: '#374151' } },
      splitLine: { lineStyle: { color: '#1f2937' } },
    }

    return {
      backgroundColor: 'transparent',
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          link: [{ xAxisIndex: 'all' }],
          label: { backgroundColor: '#374151' },
        },
        backgroundColor: '#111827',
        borderColor: '#374151',
        textStyle: { color: '#e5e7eb' },
        formatter: (params: { dataIndex: number }[]) => {
          const i = params[0]?.dataIndex ?? 0
          const c = data.curve[i]
          if (!c) return ''
          const dayRows = displayRowsByDate.get(c.date)
          const emptySeg = c.position_pct === 0
            ? emptySegs.find(s => c.date >= s.start && c.date <= s.end)
            : undefined
          let html = `<div style="font-size:11px;line-height:1.8">`
          if (emptySeg) {
            html += `<b style="color:#f59e0b">空仓段</b><br/>` +
              `${emptySeg.start} ~ ${emptySeg.end}<br/>` +
              `持续 ${emptySeg.days} 个交易日` +
              `<span style="border-top:1px solid #374151;display:block;margin:4px 0"></span>`
          }
          html += `<b>${c.date}</b><br/>` +
            `组合每份净值：<b style="color:#22c55e">${c.nav_per_share.toFixed(4)} 元</b><br/>` +
            `总资产：${fmtWan(c.nav)} 元 · 仓位：${c.position_pct.toFixed(1)}%` +
            `<span style="border-top:1px solid #374151;display:block;margin:4px 0"></span>`
          for (const etf of data.etf_series) {
            const nv = etf.nav[i]
            const dlt = etf.delta[i]
            html += `<div>${etf.name}：<b>${nv != null ? nv.toFixed(3) : '-'}</b>` +
              (dlt != null
                ? ` <span style="color:${dlt >= 0 ? '#ef4444' : '#22c55e'}">${dlt >= 0 ? '+' : ''}${dlt.toFixed(2)}亿</span>`
                : '') + `</div>`
          }
          if (dayRows) {
            html += '<span style="border-top:1px solid #374151;display:block;margin:4px 0"></span>'
            for (const t of dayRows) {
              const clr = KIND_CLR[t.kind] ?? '#9ca3af'
              const zh = KIND_ZH[t.kind] ?? t.kind
              html += `<div style="color:${clr}">${zh} ${t.name} ${t.amount.toLocaleString()} 元</div>`
            }
          }
          html += '</div>'
          return html
        },
      },
      legend: {
        data: ['每份净值(元)', '仓位%', ...data.etf_series.map(e => e.name)],
        type: 'scroll',
        textStyle: { color: '#9ca3af' },
        top: 0,
      },
      grid: [
        { left: 60, right: 70, top: 30, height: '30%' },
        { left: 60, right: 70, top: '44%', height: '26%' },
        { left: 60, right: 70, top: '76%', height: '20%', bottom: 40 },
      ],
      xAxis: [
        { type: 'category', data: dates, ...axisBase },
        { type: 'category', data: dates, gridIndex: 1, ...axisBase },
        { type: 'category', data: dates, gridIndex: 2, ...axisBase },
      ],
      yAxis: [
        { type: 'value', scale: true, ...axisBase },
        { type: 'value', min: 0, max: 100, axisLabel: { color: '#6b7280', formatter: '{value}%' }, splitLine: { show: false } },
        { type: 'value', scale: true, gridIndex: 1, ...axisBase },
        { type: 'value', scale: true, gridIndex: 2, ...axisBase, axisLabel: { color: '#6b7280', fontSize: 10, formatter: '{value}亿' } },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1, 2] },
        { type: 'slider', xAxisIndex: [0, 1, 2], bottom: 8, height: 16, borderColor: '#374151', backgroundColor: '#111827', textStyle: { color: '#6b7280' } },
      ],
      series,
    }
  }, [data, displayRowsByDate])

  const chartEvents = useMemo(() => ({
    click: (params: { componentType?: string; data?: { coord?: [string, number] } }) => {
      if (params.componentType !== 'markPoint' || !params.data?.coord) return
      const [date, posVal] = params.data.coord
      const rows = displayRowsByDate.get(date)
      if (!rows) return
      const inst = chartRef.current?.getEchartsInstance()
      const px = inst?.convertToPixel({ seriesIndex: 1 }, [date, posVal])
      if (!px) return
      const wrap = chartWrapRef.current
      const cw = wrap?.clientWidth ?? 800
      const ch = wrap?.clientHeight ?? 400
      setPopups(prev => {
        if (prev.some(p => p.key === date)) return prev
        const { left, top } = placePopup(px[0], px[1], rows, prev, cw, ch)
        return [...prev, { key: date, date, items: rows, left, top }]
      })
    },
  }), [displayRowsByDate])

  return (
    <div className="relative" ref={chartWrapRef}>
      {option && <ReactECharts ref={chartRef} option={option}
        style={{ height: isMobile ? 720 : 980 }} lazyUpdate onEvents={chartEvents} />}
      {popups.map(p => (
        <TradePopup key={p.key} popup={p}
          onClose={() => setPopups(prev => prev.filter(x => x.key !== p.key))} />
      ))}
    </div>
  )
}
