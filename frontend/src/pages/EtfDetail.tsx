import { useEffect, useMemo, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import type { ECharts } from 'echarts'
import { fetchEtfHistory } from '../api/client'
import KlineChart from '../components/KlineChart'
import SignalHistoryChart from '../components/SignalHistoryChart'
import type { ZoomWindow } from '../api/types'

const HISTORY_DAYS = 640
const SYNC_GROUP = 'etf-detail-sync'
const DEFAULT_START_DATE = '2025-12-31'

export default function EtfDetail() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({
    queryKey: ['etf', code, 'history', HISTORY_DAYS],
    queryFn: () => fetchEtfHistory(code!, HISTORY_DAYS),
    enabled: !!code,
    refetchOnWindowFocus: false,
  })

  const kline = data?.kline || []
  const signals = data?.daily_signals || []

  const dates = useMemo(() => kline.map(k => k.date), [data])
  const alignedPoints = useMemo(() => {
    const byDate = new Map(signals.map(s => [s.date, s]))
    return dates.map(d => byDate.get(d) ?? null)
  }, [data, dates])

  const initialZoom = useMemo<ZoomWindow>(() => {
    if (dates.length < 2) return { start: 0, end: 100 }
    let idx = dates.findIndex(d => d >= DEFAULT_START_DATE)
    if (idx < 0) idx = 0
    return { start: (idx / (dates.length - 1)) * 100, end: 100 }
  }, [dates])

  const klineChart = useRef<ECharts | null>(null)
  const signalChart = useRef<ECharts | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
      const el = e.target as HTMLElement | null
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) return
      const inst = klineChart.current
      if (!inst || dates.length < 2) return

      const dz = (inst.getOption().dataZoom as Array<{ start: number; end: number }>)[0]
      if (!dz) return
      e.preventDefault()

      const step = 100 / (dates.length - 1)
      const dir = e.key === 'ArrowLeft' ? -1 : 1
      const width = dz.end - dz.start
      let start = dz.start + dir * step
      let end = dz.end + dir * step
      if (start < 0) { start = 0; end = width }
      if (end > 100) { end = 100; start = 100 - width }

      const opt = { dataZoom: [{ start, end }, { start, end }] }
      klineChart.current?.setOption(opt)
      signalChart.current?.setOption(opt)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dates.length])

  if (isLoading || !data) {
    return <div className="text-gray-400 text-center py-20">加载中...</div>
  }

  const signalCount = alignedPoints.filter(p => p !== null).length

  return (
    <div className="flex flex-col h-[calc(100vh-112px)]">
      <button onClick={() => navigate('/')} className="mb-4 text-sm text-gray-400 hover:text-white shrink-0">
        ← 返回总览
      </button>
      <div className="flex items-baseline justify-between mb-1 shrink-0">
        <h2 className="text-xl font-bold">
          {data.name} <span className="text-gray-500 text-sm">{data.code}</span>
        </h2>
        <span className="text-xs text-gray-500">
          K线 {kline.length} 天 · 信号 {signalCount} 天 · 双图联动缩放 · ←/→ 逐日回放
        </span>
      </div>
      <p className="text-sm text-gray-500 mb-6 shrink-0">跟踪: {data.idx}</p>

      <div className="grid grid-cols-1 xl:grid-cols-2 grid-rows-2 xl:grid-rows-1 gap-6 flex-1 min-h-0">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col min-h-0">
          <h3 className="text-sm font-medium text-gray-300 mb-3 shrink-0">K线走势 (最长约2.5年)</h3>
          <div className="flex-1 min-h-0">
            <KlineChart kline={kline} groupId={SYNC_GROUP} height="100%" zoom={initialZoom}
              onReady={inst => { klineChart.current = inst }} />
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col min-h-0">
          <h3 className="text-sm font-medium text-gray-300 mb-3 shrink-0">综合概率信号历史</h3>
          <div className="flex-1 min-h-0">
            <SignalHistoryChart dates={dates} points={alignedPoints} groupId={SYNC_GROUP} height="100%" zoom={initialZoom}
              onReady={inst => { signalChart.current = inst }} />
          </div>
        </div>
      </div>
    </div>
  )
}
