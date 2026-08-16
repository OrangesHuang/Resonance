import { useMemo, useRef, useEffect, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import type { ECharts } from 'echarts'
import type { KlinePoint, ResonanceHistoryPoint, DailySignal, TradePoint } from '../../api/types'
import useIsMobile from '../../hooks/useIsMobile'
import type { AxisPointerBridge } from '../../hooks/useAxisPointerBridge'
import { windowToZoom, zoomToWindow, DEFAULT_VISIBLE_BARS, type DateWindow } from '../common/chartZoom'
import { computeRangeStats } from '../kline/rangeStats'
import { useRangeSelect, RangeToolbar } from '../kline/rangeSelect'
import RangeStatsPanel from '../kline/RangeStatsPanel'
import TradeReasonPanel from './TradeReasonPanel'
import { buildKlineOption } from './klineOption'

interface ClickParam {
  dataIndex?: number
  componentType?: string
  offsetX?: number
  event?: { offsetX?: number; offsetY?: number }
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

export default function ResonanceKline({ kline, history, signals, trades, selectedDate, onSelectDate, dateWindow, onZoomChange, bridge }: {
  kline: KlinePoint[]
  history: ResonanceHistoryPoint[]
  signals: DailySignal[]
  trades: TradePoint[]
  selectedDate: string | null
  onSelectDate: (date: string) => void
  dateWindow: DateWindow | null
  onZoomChange: (w: DateWindow) => void
  bridge?: AxisPointerBridge
}) {
  const chartRef = useRef<ECharts | null>(null)
  const zoomTimer = useRef<number | null>(null)
  const datesRef = useRef<string[]>([])
  const onSelectDateRef = useRef(onSelectDate)
  const onZoomChangeRef = useRef(onZoomChange)
  const bridgeRef = useRef(bridge)
  onSelectDateRef.current = onSelectDate
  onZoomChangeRef.current = onZoomChange
  bridgeRef.current = bridge
  const boundZrRef = useRef<unknown>(null)
  const onChartReady = (inst: ECharts) => {
    // chartRef 必须在 onChartReady 设置: React ref 回调在 echarts init 前
    // 执行(拿到 null), 首次缩放时 source 为空导致 K线自广播
    chartRef.current = inst
    bridgeRef.current?.register(inst, () => datesRef.current)
    // zr 事件必须在 onChartReady 绑定: echarts-for-react 首渲染的 ref
    // 回调拿到的是临时实例(随即 dispose), mount effect 绑定会失效
    const zr = inst.getZr()
    if (!zr || boundZrRef.current === zr) return
    boundZrRef.current = zr
    const zrClick = (e: { offsetX?: number }) => {
      try {
        if (e.offsetX == null) return
        // 单值形式: 二维形式在 y 超出 grid 时返回 NaN
        const px = inst.convertFromPixel({ xAxisIndex: 0 }, e.offsetX) as number | null
        const idx = px != null && !Number.isNaN(px) ? Math.round(px) : -1
        if (idx < 0 || idx >= datesRef.current.length) return
        const d = datesRef.current[idx]
        if (!d) return
        setSelectedTrade(null)
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
      } catch (err) {
        console.warn('[Kline] zr click ignored:', err)
      }
    }
    const zrMove = (e: { offsetX?: number }) => {
      const br = bridgeRef.current
      if (!br || e.offsetX == null) return
      try {
        const px = inst.convertFromPixel({ xAxisIndex: 0 }, e.offsetX) as number | null
        const idx = px != null && !Number.isNaN(px) ? Math.round(px) : -1
        const d = idx >= 0 && idx < datesRef.current.length ? datesRef.current[idx] : null
        br.show(d, inst)
      } catch {
        // 忽略坐标转换异常
      }
    }
    zr.on('click', zrClick)
    zr.on('mousemove', zrMove)
  }
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
    // key 重挂载间隙实例可能已 dispose: dispatchAction 打警告, 先探活
    try {
      inst.getZr()
    } catch {
      return
    }
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
    try {
      inst.getZr()
    } catch {
      return
    }
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
        // 买卖点标记点击 → 展示理由面板(普通点击由 zr 层处理, 任意位置可选中)
        if (params.componentType === 'markPoint' && params.data?.coord) {
          const d = params.data.coord[0]
          onSelectDateRef.current(d)
          const t = tradesByDate.get(d)
          setSelectedTrade(t ?? null)
          return
        }
        const d = params.dataIndex != null ? datesRef.current[params.dataIndex] : undefined
        if (d) onSelectDateRef.current(d)
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
    updateAxisPointer: (e: { x?: number; axisValue?: string }) => {
      // 鼠标白线悬停 → 像素转日期 → 广播到五图(按日期值对齐)
      const inst = chartRef.current
      const br = bridgeRef.current
      if (!inst || !br) return
      try {
        // 优先用 axisValue(已有日期), 否则像素转换(单值形式)
        if (e.axisValue) {
          br.show(e.axisValue, inst)
          return
        }
        if (e.x == null) return
        const px = inst.convertFromPixel({ xAxisIndex: 0 }, e.x) as number | null
        const idx = px != null && !Number.isNaN(px) ? Math.round(px) : -1
        const d = idx >= 0 && idx < datesRef.current.length ? datesRef.current[idx] : null
        br.show(d, inst)
      } catch {
        // 忽略坐标转换异常
      }
    },
    globalout: () => {
      // 鼠标移出图表 → 清除五图白线(热力图 Rect 也依赖此广播隐藏)
      bridgeRef.current?.show(null)
    },
    datazoom: (e: ZoomEvent) => {
      const z = e.batch ? e.batch[0] : e
      if (z.start == null || z.end == null) return
      // 即时广播缩放百分比到所有图(原生手感, 无 React 延迟)
      bridgeRef.current?.zoom(z.start, z.end, chartRef.current)
      const w = zoomToWindow(datesRef.current, z.start, z.end)
      if (!w) return
      // 防抖: 拖动期间只更新一次父级状态, 避免每帧重建 React 层
      if (zoomTimer.current != null) window.clearTimeout(zoomTimer.current)
      zoomTimer.current = window.setTimeout(() => {
        zoomTimer.current = null
        onZoomChangeRef.current(w)
      }, ZOOM_SYNC_DEBOUNCE_MS)
    },
  }), [rangeSel, tradesByDate, setSelectedTrade])

  if (option === null) {
    return <div className="text-gray-500 text-center py-10">暂无K线数据</div>
  }

  return (
    <div>
      <RangeToolbar hook={rangeSel} isMobile={isMobile} />
      <ReactECharts
        onChartReady={onChartReady}
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