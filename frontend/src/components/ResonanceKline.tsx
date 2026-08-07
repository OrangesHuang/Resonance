import { useMemo, useRef, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import type { ECharts } from 'echarts'
import type { KlinePoint, ResonanceHistoryPoint, DailySignal, TradePoint } from '../api/types'
import { windowToZoom, zoomToWindow, DEFAULT_VISIBLE_BARS, type DateWindow } from './chartZoom'
import { buildTradeBands, sanitizeBands } from './tradeBands'
import { computeRangeStats } from './rangeStats'
import { useRangeSelect, RangeToolbar } from './rangeSelect'
import RangeStatsPanel from './RangeStatsPanel'
import { buildKlineTooltip } from './klineTooltip'
import { buildMarks } from './klineMarks'

const AXIS_LABEL = '#6b7280'
const DANGER_BAND = 'rgba(239, 68, 68, 0.08)'
const CHANCE_BAND = 'rgba(34, 197, 94, 0.08)'
const UP_COLOR = '#ef4444'
const DOWN_COLOR = '#22c55e'

const DIR_COLORS: Record<string, string> = {
  ACCUMULATE: '#22c55e',
  DISTRIBUTE: '#ef4444',
  NEUTRAL: '#374151',
}

interface ClickParam {
  dataIndex?: number
  componentType?: string
  data?: { coord?: [string, number] }
}

interface ZoomEvent {
  start?: number
  end?: number
  batch?: Array<{ start?: number; end?: number }>
}

interface BrushEvent {
  areas?: Array<{ coordRange?: [[number, number], [number, number]] | [number, number] }>
}

const ZOOM_SYNC_DEBOUNCE_MS = 250

export default function ResonanceKline({ kline, history, signals, trades, selectedDate, onSelectDate, dateWindow, onZoomChange }: {
  kline: KlinePoint[]
  history: ResonanceHistoryPoint[]
  signals: DailySignal[]
  trades: TradePoint[]
  selectedDate: string | null
  onSelectDate: (date: string) => void
  dateWindow: DateWindow | null
  onZoomChange: (w: DateWindow) => void
}) {
  const chartRef = useRef<ECharts | null>(null)
  const zoomTimer = useRef<number | null>(null)
  const datesRef = useRef<string[]>([])
  const onSelectDateRef = useRef(onSelectDate)
  const onZoomChangeRef = useRef(onZoomChange)
  onSelectDateRef.current = onSelectDate
  onZoomChangeRef.current = onZoomChange

  // 区间统计: 点击首日→末日, 计算区间涨跌/高低/策略收益/净申赎
  const rangeSel = useRangeSelect()

  const rangeStats = useMemo(() => {
    if (!rangeSel.sel.start || !rangeSel.sel.end) return null
    return computeRangeStats(kline, trades, rangeSel.sel.start, rangeSel.sel.end, signals)
  }, [kline, trades, signals, rangeSel.sel])

  // 数据驱动的 option 用 useMemo 缓存: 拖动缩放只改 zoom, 不重建整个图表
  const option = useMemo(() => {
    if (kline.length === 0) return null
    const dates = kline.map(k => k.date)
    datesRef.current = dates
    const ohlc = kline.map(k => [k.open, k.close, k.low, k.high])
    const volumes = kline.map(k => k.volume)

    const sigByDate = new Map<string, DailySignal>()
    for (const s of signals) sigByDate.set(s.date, s)
    const flowData = dates.map(d => {
      const v = sigByDate.get(d)?.shares_delta_yi
      if (v == null) return { value: null, itemStyle: { color: '#374151' } }
      return { value: v, itemStyle: { color: v >= 0 ? DOWN_COLOR : UP_COLOR } }
    })
    const probData = dates.map(d => sigByDate.get(d)?.composite_prob ?? null)
    const dirData = dates.map(d => {
      const dir = sigByDate.get(d)?.trade_direction ?? 'NEUTRAL'
      return { value: 1, itemStyle: { color: DIR_COLORS[dir] ?? '#374151' } }
    })

    const bands = sanitizeBands(
      history
        .filter(h => h.red >= 3 || h.green >= 3)
        .map(h => [
          { xAxis: h.date, itemStyle: { color: h.red >= 3 ? DANGER_BAND : CHANCE_BAND } },
          { xAxis: h.date },
        ]),
      dates,
    )

    // 买卖点区间蒙布: 持仓段淡绿 / 空仓段淡红
    const tradeBands = sanitizeBands(buildTradeBands(trades, dates[dates.length - 1]), dates)
    // 区间统计蒙版: rangeSel.band 是 [首日, 末日] 二元组, 必须整体传入不可展开
    const rangeBand = rangeSel.band.length ? sanitizeBands([rangeSel.band] as never[], dates) : []

    // 区间统计激活: 禁用 inside 拖拽平移(拖拽=框选)
    // 注意: ECharts merge 语义下未显式字段会残留旧值,
    // 关闭时必须显式设回 moveOnMouseMove: true 否则拖移永久失效
    const brushActive = rangeSel.mode
    const insideZoom = brushActive
      ? { type: 'inside' as const, xAxisIndex: [0, 1, 2, 3, 4], moveOnMouseMove: false }
      : { type: 'inside' as const, xAxisIndex: [0, 1, 2, 3, 4], moveOnMouseMove: true }

    const { markPoint, markLine, markLineTop, probMarkLine } =
      buildMarks(trades, kline, dates, selectedDate)

    const tradeByDate = new Map(trades.map(t => [t.date, t]))
    const tooltipFormatter = buildKlineTooltip(kline, sigByDate, tradeByDate, rangeStats)

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
      visualMap: {
        show: false,
        seriesIndex: 3,
        dimension: 1,
        pieces: [
          { lte: 50, color: '#22c55e' },
          { gt: 50, lte: 70, color: '#f59e0b' },
          { gt: 70, color: '#ef4444' },
        ],
        outOfRange: { color: '#6b7280' },
      },
      grid: [
        { left: 60, right: 20, top: 20, height: '34%' },
        { left: 60, right: 20, top: '52%', height: '7%' },
        { left: 60, right: 20, top: '62%', height: '7%' },
        { left: 60, right: 20, top: '72%', height: '9%' },
        { left: 60, right: 20, top: '84%', height: '4%' },
      ],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0, boundaryGap: true, axisLabel: { color: AXIS_LABEL, fontSize: 10 } },
        { type: 'category', data: dates, gridIndex: 1, boundaryGap: true, axisLabel: { show: false } },
        { type: 'category', data: dates, gridIndex: 2, boundaryGap: true, axisLabel: { show: false } },
        { type: 'category', data: dates, gridIndex: 3, boundaryGap: false, axisLabel: { show: false } },
        { type: 'category', data: dates, gridIndex: 4, boundaryGap: true, axisLabel: { show: false } },
      ],
      yAxis: [
        { scale: true, gridIndex: 0, boundaryGap: ['8%', '8%'], splitLine: { lineStyle: { color: '#1f2937' } }, axisLabel: { color: AXIS_LABEL } },
        { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false } },
        { scale: true, gridIndex: 2, splitLine: { show: false }, axisLabel: { color: AXIS_LABEL, fontSize: 9 } },
        { min: 0, max: 100, gridIndex: 3, splitNumber: 2, splitLine: { show: false }, axisLabel: { color: AXIS_LABEL, fontSize: 9, formatter: '{value}%' } },
        { min: 0, max: 1, gridIndex: 4, splitLine: { show: false }, axisLabel: { show: false } },
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: ohlc,
          xAxisIndex: 0,
          yAxisIndex: 0,
          itemStyle: {
            color: UP_COLOR,
            color0: DOWN_COLOR,
            borderColor: UP_COLOR,
            borderColor0: DOWN_COLOR,
          },
          markArea: { silent: true, data: sanitizeBands([...bands, ...tradeBands, ...rangeBand] as never[], dates) },
          markLine: markLineTop,
          markPoint,
        },
        {
          name: '成交量',
          type: 'bar',
          data: volumes,
          xAxisIndex: 1,
          yAxisIndex: 1,
          itemStyle: { color: '#4b5563' },
          markLine,
        },
        {
          name: '份额净申赎(亿份)',
          type: 'bar',
          data: flowData,
          xAxisIndex: 2,
          yAxisIndex: 2,
          markLine,
        },
        {
          name: '综合概率',
          type: 'line',
          data: probData,
          xAxisIndex: 3,
          yAxisIndex: 3,
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 1.5 },
          areaStyle: { opacity: 0.08 },
          markLine: probMarkLine,
        },
        {
          name: '交易方向',
          type: 'bar',
          data: dirData,
          xAxisIndex: 4,
          yAxisIndex: 4,
          barWidth: '60%',
          markLine,
        },
      ],
      dataZoom: [
        insideZoom,
        {
          type: 'slider',
          xAxisIndex: [0, 1, 2, 3, 4],
          top: '92%',
          height: 16,
          borderColor: '#374151',
          backgroundColor: '#111827',
          fillerColor: 'rgba(75, 118, 99, 0.3)',
          handleStyle: { color: '#6b7280' },
          textStyle: { color: '#6b7280' },
        },
      ],
    }
  }, [kline, signals, history, trades, selectedDate, rangeSel.sel, rangeSel.mode])

  // 外部缩放(键盘步进/切换标的)经 dispatchAction 同步, 不走 option 重建
  useEffect(() => {
    const inst = chartRef.current
    if (!inst || kline.length <= 1) return
    const { start, end } = windowToZoom(datesRef.current, dateWindow, DEFAULT_VISIBLE_BARS)
    inst.dispatchAction({ type: 'dataZoom', start, end })
  }, [dateWindow, kline])

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

  const onEvents = useMemo(() => ({
    click: (params: ClickParam) => {
      try {
        if (params.componentType === 'markPoint' && params.data?.coord) {
          onSelectDateRef.current(params.data.coord[0])
          return
        }
        const d = params.dataIndex != null ? datesRef.current[params.dataIndex] : undefined
        if (!d) return
        // 区间统计激活时, 点击仅选中日期(框选由 brushEnd 负责)
        onSelectDateRef.current(d)
      } catch (e) {
        // 忽略 ECharts 事件参数异常(部分版本 markPoint 事件 data 结构差异)
        console.warn('[Kline] click handler ignored:', e)
      }
    },
    brushEnd: (e: BrushEvent) => {
      const area = e.areas?.[0]
      const cr = area?.coordRange as [[number, number], [number, number]] | [number, number] | undefined
      if (!cr) return
      // rect 的 coordRange 为 [[x0,x1],[y0,y1]] 嵌套数组(见 BrushTargetManager)
      const xRange: [number, number] = typeof cr[0] === 'number'
        ? (cr as [number, number])
        : (cr[0] as unknown as [number, number])
      const [a, b] = [Math.round(xRange[0]), Math.round(xRange[1])]
      const dates = datesRef.current
      if (a < 0 || b < 0 || a >= dates.length || b >= dates.length) return
      rangeSel.setRange(dates[a], dates[b])
    },
    datazoom: (e: ZoomEvent) => {
      const z = e.batch ? e.batch[0] : e
      if (z.start == null || z.end == null) return
      const w = zoomToWindow(datesRef.current, z.start, z.end)
      if (!w) return
      // 防抖: 拖动期间只更新一次父级状态, 避免每帧重建 React 层
      if (zoomTimer.current != null) window.clearTimeout(zoomTimer.current)
      zoomTimer.current = window.setTimeout(() => {
        zoomTimer.current = null
        onZoomChangeRef.current(w)
      }, ZOOM_SYNC_DEBOUNCE_MS)
    },
  }), [])

  if (option === null) {
    return <div className="text-gray-500 text-center py-10">暂无K线数据</div>
  }

  return (
    <div>
      <RangeToolbar hook={rangeSel} />
      <ReactECharts
        ref={inst => { chartRef.current = inst?.getEchartsInstance?.() ?? null }}
        option={option}
        style={{ height: 620, cursor: 'pointer' }}
        lazyUpdate
        onEvents={onEvents}
      />
      {rangeStats && (
        <RangeStatsPanel stats={rangeStats} onClear={rangeSel.clear} />
      )}
    </div>
  )
}
