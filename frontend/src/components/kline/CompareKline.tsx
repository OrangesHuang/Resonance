import { useMemo, useRef, useEffect, useCallback } from 'react'
import ReactECharts from 'echarts-for-react'
import type { ECharts } from 'echarts'
import type { KlinePoint, TradePoint, DailySignal } from '../../api/types'
import useIsMobile from '../../hooks/useIsMobile'
import { computeRangeStats } from './rangeStats'
import { useRangeSelect, RangeToolbar } from './rangeSelect'
import RangeStatsPanel from './RangeStatsPanel'
import { buildCompareOption } from './compareOption'

interface ClickParam {
  dataIndex?: number
  componentType?: string
}

interface BrushEvent {
  areas?: Array<{ coordRange?: [[number, number], [number, number]] | [number, number] }>
}

interface ZoomEvent {
  batch?: Array<{ start?: number; end?: number }>
  start?: number
  end?: number
}

export interface ZoomRange {
  start: number
  end: number
}

// 回声过滤容差: datazoom 事件值 ≈ 自己最近转发的值时视为同步回显, 忽略防转发级联循环
const ZOOM_ECHO_EPS = 0.05

export default function CompareKline({ kline, trades, signals, sharedDates, height = 320, code, onZoomChange, onRegister, onUnmount }: {
  kline: KlinePoint[]
  trades: TradePoint[]
  signals?: DailySignal[]
  sharedDates?: string[]
  height?: number
  code: string
  onZoomChange: (z: ZoomRange) => void
  onRegister: (code: string, inst: ECharts) => void
  onUnmount: (code: string) => void
}) {
  const datesRef = useRef<string[]>([])
  const chartRef = useRef<ECharts | null>(null)
  const rangeSel = useRangeSelect()
  const isMobile = useIsMobile()
  const mobileRangeStart = useRef<string | null>(null)
  const isMobileRef = useRef(isMobile)
  isMobileRef.current = isMobile
  const rangeSelRef = useRef(rangeSel)
  rangeSelRef.current = rangeSel
  const onZoomChangeRef = useRef(onZoomChange)
  onZoomChangeRef.current = onZoomChange
  const onRegisterRef = useRef(onRegister)
  onRegisterRef.current = onRegister
  const onUnmountRef = useRef(onUnmount)
  onUnmountRef.current = onUnmount
  // 本图最近一次转发的缩放值: 收到相等值的事件 → 同步回显, 不再转发
  const lastForwardRef = useRef<ZoomRange | null>(null)
  // rAF 待转发值: 一帧内多次 datazoom 事件合并为最后一次转发, 其余图与拖动同步移动
  const pendingZoomRef = useRef<ZoomRange | null>(null)
  const rafRef = useRef<number | null>(null)

  const rangeStats = useMemo(() => {
    if (!rangeSel.sel.start || !rangeSel.sel.end) return null
    return computeRangeStats(kline, trades, rangeSel.sel.start, rangeSel.sel.end)
  }, [kline, trades, rangeSel])

  // 数据驱动的 option 用 useMemo 缓存: 缩放走 dispatchAction, 不重建图表
  const { option, dates } = useMemo(() =>
    buildCompareOption({ kline, trades, signals, sharedDates, rangeSel, rangeStats, isMobile }),
  [kline, trades, signals, sharedDates, rangeSel, rangeStats, isMobile])

  useEffect(() => {
    datesRef.current = dates
  }, [dates])

  // 挂载注册 / 卸载注销: 注册幂等(map.set + 同步一次全局缩放)。
  // 注销放 ref 回调的 null 分支而非 cleanup effect —— StrictMode 模拟卸载只重放
  // effects, 若在 cleanup 里注销, 图表不会再重新注册, 实例 Map 变空导致全不联动
  const handleChartRef = useCallback((inst: ReactECharts | null) => {
    const i = inst?.getEchartsInstance?.() ?? null
    chartRef.current = i
    if (i) onRegisterRef.current(code, i)
    else onUnmountRef.current(code)
  }, [code])

  useEffect(() => () => {
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
  }, [code])

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
    datazoom: (e: ZoomEvent) => {
      const z = e.batch ? e.batch[0] : e
      const start = z.start
      const end = z.end
      if (start == null || end == null) return
      // 回声过滤: 值等于自己最近转发的值 → dispatchAction 同步回显, 不再转发
      const last = lastForwardRef.current
      if (last && Math.abs(last.start - start) < ZOOM_ECHO_EPS && Math.abs(last.end - end) < ZOOM_ECHO_EPS) return
      // rAF 节流: 帧内多次事件只转发最后一次, 其余图与拖动同步移动
      if (pendingZoomRef.current == null) {
        pendingZoomRef.current = { start, end }
        rafRef.current = requestAnimationFrame(() => {
          rafRef.current = null
          const zz = pendingZoomRef.current
          pendingZoomRef.current = null
          if (!zz) return
          lastForwardRef.current = zz
          onZoomChangeRef.current(zz)
        })
      } else {
        pendingZoomRef.current = { start, end }
      }
    },
  }), [rangeSel])

  if (option === null) {
    return <div className="text-gray-500 text-center py-8 text-sm">暂无K线数据</div>
  }

  return (
    <div>
      <RangeToolbar hook={rangeSel} isMobile={isMobile} />
      <ReactECharts
        ref={handleChartRef}
        option={option} style={{ height }} lazyUpdate onEvents={onEvents} />
      {rangeStats && (
        <RangeStatsPanel stats={rangeStats} onClear={rangeSel.clear} />
      )}
    </div>
  )
}
