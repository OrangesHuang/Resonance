import { useMemo, useRef, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import * as echarts from 'echarts'
import type { KlinePoint, TradePoint, DailySignal } from '../api/types'
import useIsMobile from '../hooks/useIsMobile'
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

export default function CompareKline({ kline, trades, signals, sharedDates, height = 320, groupId, onReady }: {
  kline: KlinePoint[]
  trades: TradePoint[]
  signals?: DailySignal[]
  sharedDates?: string[]
  height?: number
  groupId?: string
  onReady?: (inst: echarts.ECharts) => void
}) {
  const datesRef = useRef<string[]>([])
  const chartRef = useRef<import('echarts').ECharts | null>(null)
  const rangeSel = useRangeSelect()
  const isMobile = useIsMobile()
  const mobileRangeStart = useRef<string | null>(null)
  const isMobileRef = useRef(isMobile)
  isMobileRef.current = isMobile
  const rangeSelRef = useRef(rangeSel)
  rangeSelRef.current = rangeSel

  // 区间统计模式切换: 桌面端启用 brush 光标; 移动端清除待选状态
  useEffect(() => {
    if (isMobile) {
      mobileRangeStart.current = null
      return
    }
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
  }, [rangeSel.mode, isMobile])

  const rangeStats = useMemo(() => {
    if (!rangeSel.sel.start || !rangeSel.sel.end) return null
    return computeRangeStats(kline, trades, rangeSel.sel.start, rangeSel.sel.end)
  }, [kline, trades, rangeSel.sel])

  const option = useMemo(() => {
    if (kline.length === 0) return null
    const dates = sharedDates ?? kline.map(k => k.date)
    datesRef.current = dates
    const klineByDate = new Map(kline.map(k => [k.date, k]))
    const ohlc = dates.map(d => {
      const k = klineByDate.get(d)
      return k ? [k.open, k.close, k.low, k.high] : '-'
    })
    const volumes = dates.map(d => klineByDate.get(d)?.volume ?? null)
    const ma20 = dates.map((_, i) => {
      const lo = Math.max(0, i - 19)
      const win: number[] = []
      for (let j = lo; j <= i; j++) {
        const k = klineByDate.get(dates[j])
        if (k) win.push(k.close)
      }
      return win.length ? Number((win.reduce((s, v) => s + v, 0) / win.length).toFixed(3)) : null
    })

    const tradesByDate = new Map(trades.map(t => [t.date, t]))
    const tradeBands = sanitizeBands(buildTradeBands(trades, dates[dates.length - 1]), dates)
    const signalMap = new Map((signals ?? []).map(s => [s.date, s]))
    const hasShares = signalMap.size > 0
    const xAxisAll = hasShares ? [0, 1, 2] : [0, 1]
    // 区间统计激活: 禁用 inside 拖拽平移(拖拽=框选)
    // 移动端: 不使用 brush, 改用两次点击选区间
    const brushActive = rangeSel.mode && !isMobile
    const insideZoom = brushActive
      ? { type: 'inside' as const, xAxisIndex: xAxisAll, moveOnMouseMove: false }
      : { type: 'inside' as const, xAxisIndex: xAxisAll, moveOnMouseMove: true, preventDefaultMouseMove: true }
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
      const d = i != null ? dates[i] : undefined
      const k = d ? klineByDate.get(d) : undefined
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
      const sig = signalMap.get(k.date)
      const shareHtml = sig?.shares_delta_yi != null
        ? `<br/>净申赎：<span style="color:${sig.shares_delta_yi! >= 0 ? '#22c55e' : '#ef4444'};font-weight:bold">${sig.shares_delta_yi! >= 0 ? '+' : ''}${sig.shares_delta_yi!.toFixed(2)} 亿份</span>`
        : ''
      return `<div style="font-size:11px;line-height:1.8">` +
        `<b>${k.date}</b><br/>` +
        `开 ${k.open} · 收 ${k.close} · 高 ${k.high} · 低 ${k.low}<br/>` +
        `成交量：${k.volume.toLocaleString('zh-CN')}` +
        tradeHtml +
        shareHtml +
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
        brushType: brushActive ? 'rect' : false,
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
      grid: hasShares
        ? [
            { left: 55, right: 16, top: 12, height: '55%' },
            { left: 55, right: 16, top: '70%', height: '10%' },
            { left: 55, right: 16, top: '83%', height: '10%' },
          ]
        : [
            { left: 55, right: 16, top: 12, height: '66%' },
            { left: 55, right: 16, top: '82%', height: '11%' },
          ],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0, boundaryGap: true, axisLabel: { color: '#6b7280', fontSize: 10 } },
        { type: 'category', data: dates, gridIndex: 1, boundaryGap: true, axisLabel: { show: false } },
        ...(hasShares ? [{ type: 'category' as const, data: dates, gridIndex: 2, boundaryGap: true, axisLabel: { show: false } }] : []),
      ],
      yAxis: [
        { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: '#1f2937' } }, axisLabel: { color: '#6b7280' } },
        { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false } },
        ...(hasShares ? [{ scale: true, gridIndex: 2, splitLine: { show: false }, axisLabel: { show: false } }] : []),
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
        ...(hasShares ? [{
          name: '净申赎',
          type: 'bar',
          data: dates.map(d => {
            const v = signalMap.get(d)?.shares_delta_yi
            return { value: v ?? 0, itemStyle: { color: (v ?? 0) >= 0 ? '#22c55e' : '#ef4444' } }
          }),
          xAxisIndex: 2,
          yAxisIndex: 2,
        }] : []),
      ],
      dataZoom: [
        insideZoom,
        {
          type: 'slider',
          xAxisIndex: xAxisAll,
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
  }, [kline, trades, signals, sharedDates, rangeSel.sel, rangeSel.mode])

  const onEvents = useMemo(() => ({
    click: (params: ClickParam) => {
      try {
        const d = params.dataIndex != null ? datesRef.current[params.dataIndex] : undefined
        if (!d) return
        // 移动端区间统计: 两次点击选区间
        if (isMobileRef.current && rangeSelRef.current.mode) {
          const rs = rangeSelRef.current
          if (mobileRangeStart.current == null) {
            mobileRangeStart.current = d
          } else {
            rs.setRange(mobileRangeStart.current, d)
            mobileRangeStart.current = null
          }
          return
        }
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
      <RangeToolbar hook={rangeSel} isMobile={isMobile} />
      <ReactECharts
        ref={inst => { chartRef.current = inst?.getEchartsInstance?.() ?? null }}
        option={option} style={{ height }} lazyUpdate onEvents={onEvents}
        onChartReady={inst => {
          if (groupId) { inst.group = groupId; echarts.connect(groupId) }
          onReady?.(inst)
        }} />
      {rangeStats && (
        <RangeStatsPanel stats={rangeStats} onClear={rangeSel.clear} />
      )}
    </div>
  )
}
