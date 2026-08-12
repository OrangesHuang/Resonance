import { useMemo, useRef, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import * as echarts from 'echarts'
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

  const rangeStats = useMemo(() => {
    if (!rangeSel.sel.start || !rangeSel.sel.end) return null
    return computeRangeStats(kline, trades, rangeSel.sel.start, rangeSel.sel.end)
  }, [kline, trades, rangeSel])

  // 数据驱动的 option 用 useMemo 缓存: 拖动缩放只改 zoom, 不重建整个图表
  const { option, dates } = useMemo(() =>
    buildCompareOption({ kline, trades, signals, sharedDates, rangeSel, rangeStats, isMobile }),
  [kline, trades, signals, sharedDates, rangeSel, rangeStats, isMobile])

  useEffect(() => {
    datesRef.current = dates
  }, [dates])

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
  }), [rangeSel])

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
