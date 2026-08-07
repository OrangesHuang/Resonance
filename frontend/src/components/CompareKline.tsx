import { useMemo, useRef, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import type { KlinePoint, TradePoint } from '../api/types'
import { buildTradeBands, sanitizeBands } from './tradeBands'
import { computeRangeStats } from './rangeStats'
import { useRangeSelect, RangeToolbar } from './rangeSelect'
import RangeStatsPanel from './RangeStatsPanel'

interface TooltipParam {
  dataIndex?: number
}

interface ClickParam {
  dataIndex?: number
  componentType?: string
}

interface BrushEvent {
  areas?: Array<{ coordRange?: [[number, number], [number, number]] | [number, number] }>
}

export default function CompareKline({ kline, trades, height = 320 }: {
  kline: KlinePoint[]
  trades: TradePoint[]
  height?: number
}) {
  const datesRef = useRef<string[]>([])
  const chartRef = useRef<import('echarts').ECharts | null>(null)
  const rangeSel = useRangeSelect()

  // 区间统计激活时自动启用 brush 光标(免去每次点 toolbox 按钮)
  useEffect(() => {
    const inst = chartRef.current
    if (!inst) return
    inst.dispatchAction({
      type: 'takeGlobalCursor',
      key: 'brush',
      brushOption: rangeSel.mode ? { brushType: 'rect' } : { brushType: false },
    })
    if (!rangeSel.mode) {
      inst.dispatchAction({ type: 'brush', command: 'clear', areas: [] })
    }
  }, [rangeSel.mode, rangeSel.sel])

  const rangeStats = useMemo(() => {
    if (!rangeSel.sel.start || !rangeSel.sel.end) return null
    return computeRangeStats(kline, trades, rangeSel.sel.start, rangeSel.sel.end)
  }, [kline, trades, rangeSel.sel])

  const option = useMemo(() => {
    if (kline.length === 0) return null
    const dates = kline.map(k => k.date)
    datesRef.current = dates
    const ohlc = kline.map(k => [k.open, k.close, k.low, k.high])
    const volumes = kline.map(k => k.volume)
    const ma20 = kline.map((_, i) => {
      const lo = Math.max(0, i - 19)
      const win = kline.slice(lo, i + 1)
      return Number((win.reduce((s, k) => s + k.close, 0) / win.length).toFixed(3))
    })

    const klineByDate = new Map(kline.map(k => [k.date, k]))
    const tradesByDate = new Map(trades.map(t => [t.date, t]))
    const tradeBands = sanitizeBands(buildTradeBands(trades, dates[dates.length - 1]), dates)
    // 区间统计激活: 禁用 inside 拖拽平移(拖拽=框选)
    // 注意: ECharts merge 语义下未显式字段会残留旧值,
    // 关闭时必须显式设回 moveOnMouseMove: true 否则拖移永久失效
    const brushActive = rangeSel.mode
    const insideZoom = brushActive
      ? { type: 'inside' as const, xAxisIndex: [0, 1], moveOnMouseMove: false }
      : { type: 'inside' as const, xAxisIndex: [0, 1], moveOnMouseMove: true }
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
      let rangeHtml = ''
      if (rangeStats) {
        const flow = rangeStats.net_flow_yi
        const flowHtml = flow == null
          ? '区间净申赎：-'
          : `区间净申赎：<span style="color:${flow >= 0 ? '#22c55e' : '#ef4444'};font-weight:bold">` +
            `${flow >= 0 ? '+' : ''}${flow.toFixed(2)} 亿份</span>`
        rangeHtml = `<div style="margin-top:6px;padding-top:5px;border-top:1px dashed #374151">` +
          `<b>区间 ${rangeStats.start} ~ ${rangeStats.end}</b><br/>` +
          `涨跌幅：<span style="color:${rangeStats.change_pct >= 0 ? '#ef4444' : '#22c55e'};font-weight:bold">` +
          `${rangeStats.change_pct >= 0 ? '+' : ''}${rangeStats.change_pct.toFixed(1)}%</span>` +
          `（首日收 ${rangeStats.start_close.toFixed(3)} → 末日收 ${rangeStats.end_close.toFixed(3)}）<br/>` +
          `${flowHtml}<br/>` +
          `振幅：${rangeStats.amplitude_pct >= 0 ? '+' : ''}${rangeStats.amplitude_pct.toFixed(1)}%</div>`
      }
      return `<div style="font-size:11px;line-height:1.8">` +
        `<b>${k.date}</b><br/>` +
        `开 ${k.open} · 收 ${k.close} · 高 ${k.high} · 低 ${k.low}<br/>` +
        `成交量：${k.volume.toLocaleString('zh-CN')}` +
        tradeHtml +
        rangeHtml +
        `</div>`
    }

    return {
      backgroundColor: 'transparent',
      animation: false,
      // brushType 随 mode 动态化: 激活 rect / 关闭 false
      // (写死 rect 会在关闭后的任何 setOption 时重新激活 brush 占用
      //  globalPan 互斥锁, 导致 dataZoom 拖拽平移失效)
      brush: {
        xAxisIndex: 0,
        yAxisIndex: 0,
        brushType: rangeSel.mode ? 'rect' : false,
        brushMode: 'single',
        brushStyle: {
          borderColor: '#0ea5e9',
          color: 'rgba(56, 189, 248, 0.10)',
          borderWidth: 1,
        },
        throttleType: 'debounce',
        throttleDelay: 60,
        removeOnClick: false,
      },
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
          markArea: { silent: true, data: sanitizeBands([...tradeBands, ...(rangeSel.band.length ? [rangeSel.band] : [])] as never[], dates) },
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
        insideZoom,
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
  }, [kline, trades, rangeSel.sel, rangeSel.mode])

  const onEvents = useMemo(() => ({
    click: (params: ClickParam) => {
      try {
        const d = params.dataIndex != null ? datesRef.current[params.dataIndex] : undefined
        if (!d) return
        // 区间统计激活时点击不改变区间(框选由 brushEnd 负责)
      } catch (e) {
        console.warn('[Kline] click handler ignored:', e)
      }
    },
    brushEnd: (e: BrushEvent) => {
      const area = e.areas?.[0]
      const cr = area?.coordRange as [[number, number], [number, number]] | [number, number] | undefined
      if (!cr) return
      // rect 的 coordRange 为 [[x0,x1],[y0,y1]] 嵌套数组
      const xRange: [number, number] = typeof cr[0] === 'number'
        ? (cr as [number, number])
        : (cr[0] as unknown as [number, number])
      const [a, b] = [Math.round(xRange[0]), Math.round(xRange[1])]
      const dates = datesRef.current
      if (a < 0 || b < 0 || a >= dates.length || b >= dates.length) return
      rangeSel.setRange(dates[a], dates[b])
    },
  }), [])

  if (option === null) {
    return <div className="text-gray-500 text-center py-8 text-sm">暂无K线数据</div>
  }

  return (
    <div>
      <RangeToolbar hook={rangeSel} />
      <ReactECharts
        ref={inst => { chartRef.current = inst?.getEchartsInstance?.() ?? null }}
        option={option} style={{ height }} lazyUpdate onEvents={onEvents} />
      {rangeStats && (
        <RangeStatsPanel stats={rangeStats} onClear={rangeSel.clear} />
      )}
    </div>
  )
}
