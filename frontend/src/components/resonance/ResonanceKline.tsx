import { useMemo, useRef, useEffect, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import type { ECharts } from 'echarts'
import type { KlinePoint, ResonanceHistoryPoint, DailySignal, TradePoint } from '../../api/types'
import useIsMobile from '../../hooks/useIsMobile'
import { useChartSync, RESONANCE_SYNC_GROUP } from '../../hooks/useChartSync'
import { windowToZoom, zoomToWindow, DEFAULT_VISIBLE_BARS, type DateWindow } from '../common/chartZoom'
import { computeRangeStats } from '../kline/rangeStats'
import { useRangeSelect, RangeToolbar } from '../kline/rangeSelect'
import RangeStatsPanel from '../kline/RangeStatsPanel'
import TradeReasonPanel from './TradeReasonPanel'
import { buildKlineOption } from './klineOption'

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
  const onChartReady = useChartSync(RESONANCE_SYNC_GROUP)
  const isMobile = useIsMobile()
  const mobileRangeStart = useRef<string | null>(null)
  const isMobileRef = useRef(isMobile)
  isMobileRef.current = isMobile

  // 区间统计: 点击首日→末日, 计算区间涨跌/高低/策略收益/净申赎
  const rangeSel = useRangeSelect()
  const rangeSelRef = useRef(rangeSel)
  rangeSelRef.current = rangeSel

  const rangeStats = useMemo(() => {
    if (!rangeSel.sel.start || !rangeSel.sel.end) return null
    return computeRangeStats(kline, trades, rangeSel.sel.start, rangeSel.sel.end, signals)
  }, [kline, trades, signals, rangeSel])

  // 点击买卖点标记 → 展示该日完整理由(量能/份额/位置证据链)
  const [selectedTrade, setSelectedTrade] = useState<TradePoint | null>(null)
  const tradesByDate = useMemo(() => new Map(trades.map(t => [t.date, t])), [trades])
  const sigByDate = useMemo(() => new Map(signals.map(s => [s.date, s])), [signals])
  const klineByDate = useMemo(() => new Map(kline.map(k => [k.date, k])), [kline])

  // 数据驱动的 option 用 useMemo 缓存: 拖动缩放只改 zoom, 不重建整个图表
  const { option, dates } = useMemo(() =>
    buildKlineOption({ kline, history, signals, trades, selectedDate, rangeSel, rangeStats, isMobile }),
  [kline, signals, history, trades, selectedDate, rangeSel, rangeStats, isMobile])

  useEffect(() => {
    datesRef.current = dates
  }, [dates])

  // 外部缩放(键盘步进/切换标的)经 dispatchAction 同步, 不走 option 重建
  useEffect(() => {
    const inst = chartRef.current
    if (!inst || kline.length <= 1) return
    const { start, end } = windowToZoom(datesRef.current, dateWindow, DEFAULT_VISIBLE_BARS)
    inst.dispatchAction({ type: 'dataZoom', start, end })
  }, [dateWindow, kline])

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

  const onEvents = useMemo(() => ({
    click: (params: ClickParam) => {
      try {
        if (params.componentType === 'markPoint' && params.data?.coord) {
          const d = params.data.coord[0]
          onSelectDateRef.current(d)
          const t = tradesByDate.get(d)
          setSelectedTrade(t ?? null)
          return
        }
        const d = params.dataIndex != null ? datesRef.current[params.dataIndex] : undefined
        if (!d) return
        setSelectedTrade(null)
        // 移动端区间统计: 两次点击选区间(代替桌面端拖拽框选)
        if (isMobileRef.current && rangeSelRef.current.mode) {
          const rs = rangeSelRef.current
          if (mobileRangeStart.current == null) {
            mobileRangeStart.current = d
            onSelectDateRef.current(d)
          } else {
            rs.setRange(mobileRangeStart.current, d)
            mobileRangeStart.current = null
          }
          return
        }
        onSelectDateRef.current(d)
      } catch (e) {
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
  }), [rangeSel, tradesByDate])

  if (option === null) {
    return <div className="text-gray-500 text-center py-10">暂无K线数据</div>
  }

  return (
    <div>
      <RangeToolbar hook={rangeSel} isMobile={isMobile} />
      <ReactECharts
        onChartReady={onChartReady}
        ref={inst => { chartRef.current = inst?.getEchartsInstance?.() ?? null }}
        option={option}
        style={{ height: isMobile ? 400 : 620, cursor: 'pointer' }}
        lazyUpdate
        onEvents={onEvents}
      />
      {rangeStats && (
        <RangeStatsPanel stats={rangeStats} onClear={rangeSel.clear} />
      )}
      {selectedTrade && (
        <TradeReasonPanel
          trade={selectedTrade}
          signal={sigByDate.get(selectedTrade.date)}
          kline={klineByDate.get(selectedTrade.date)}
          onClose={() => setSelectedTrade(null)}
        />
      )}
    </div>
  )
}
