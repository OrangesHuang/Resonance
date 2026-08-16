import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { useResonance } from '../hooks/useResonance'
import { fetchEtfList, fetchEtfHistory, fetchResonanceTrades, fetchStrategyVersions, refreshEtf } from '../api/client'
import ResonanceLights from '../components/resonance/ResonanceLights'
import ResonanceKline from '../components/resonance/ResonanceKline'
import ResonanceChart from '../components/resonance/ResonanceChart'
import ResonanceHeatmap from '../components/resonance/ResonanceHeatmap'
import ResonanceEvidencePanel, { type ResonanceSelection } from '../components/resonance/ResonanceEvidencePanel'
import ResonanceMethodNote from '../components/resonance/ResonanceMethodNote'
import MarketSentimentSection from '../components/resonance/MarketSentimentSection'
import EtfSelector from '../components/common/EtfSelector'
import { useAxisPointerBridge } from '../hooks/useAxisPointerBridge'
import { DEFAULT_VISIBLE_BARS, type DateWindow } from '../components/common/chartZoom'
import { unionDates, alignKlineToDates, alignResonanceHistoryToDates } from '../components/resonance/alignChartDates'

const KLINE_DAYS = 2000  // 覆盖 2021 至今历史(2021-01 起约 1370 个交易日)

export default function Resonance() {
  const [code, setCode] = useState('510300')  // 默认沪深300
  const [algoVersion, setAlgoVersion] = useState<'stable' | 'beta'>('stable')  // 算法版本: 正式版/Beta
  const [selected, setSelected] = useState<ResonanceSelection | null>(null)
  const [dateWindow, setDateWindow] = useState<DateWindow | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const bridge = useAxisPointerBridge()
  const queryClient = useQueryClient()

  const { data, isLoading, error, refetch } = useResonance(code)
  const { data: etfList } = useQuery({
    queryKey: ['etfList'],
    queryFn: fetchEtfList,
    staleTime: Infinity,
  })
  const { data: history } = useQuery({
    queryKey: ['etfHistory', code],
    queryFn: () => fetchEtfHistory(code, KLINE_DAYS),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60 * 1000,
  })
  const { data: tradesData } = useQuery({
    queryKey: ['resonanceTrades', code, algoVersion],
    queryFn: () => fetchResonanceTrades(code, algoVersion),
    staleTime: 30 * 1000,
  })
  const { data: strategyVersions } = useQuery({
    queryKey: ['strategyVersions'],
    queryFn: fetchStrategyVersions,
    staleTime: 5 * 60 * 1000,
  })
  const hasBeta = strategyVersions?.[code] ?? false

  const tradeDates = useMemo(() => history?.kline.map(k => k.date) ?? [], [history])
  const klineStart = tradeDates[0] ?? null
  const displayDate = selected?.date ?? data?.date ?? tradeDates[tradeDates.length - 1] ?? ''
  const curIdx = displayDate ? tradeDates.indexOf(displayDate) : -1
  const canPrev = curIdx === -1 ? tradeDates.length > 1 : curIdx > 0
  const canNext = curIdx >= 0 && curIdx < tradeDates.length - 1

  const stepDay = useCallback((dir: number) => {
    if (tradeDates.length === 0) return
    const idx = curIdx === -1 ? tradeDates.length - 1 : curIdx
    const nextIdx = idx + dir
    if (nextIdx < 0 || nextIdx >= tradeDates.length) return
    const nextDate = tradeDates[nextIdx]
    setSelected({ date: nextDate, indicator: null })
    const win = dateWindow ??
      { start: tradeDates[Math.max(0, tradeDates.length - DEFAULT_VISIBLE_BARS)], end: tradeDates[tradeDates.length - 1] }
    const sIdx = tradeDates.indexOf(win.start)
    const eIdx = tradeDates.indexOf(win.end)
    if (sIdx < 0 || eIdx < 0) return
    const span = eIdx - sIdx
    if (nextIdx > eIdx) setDateWindow({ start: tradeDates[nextIdx - span], end: nextDate })
    else if (nextIdx < sIdx) setDateWindow({ start: nextDate, end: tradeDates[nextIdx + span] })
  }, [tradeDates, curIdx, dateWindow])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLElement && ['SELECT', 'INPUT', 'TEXTAREA'].includes(e.target.tagName)) return
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
      e.preventDefault()
      stepDay(e.key === 'ArrowLeft' ? -1 : 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [stepDay])

  // useMemo 缓存: 避免每次渲染新引用导致子图表高频 setOption
  // ("setOption should not be called during main process" 根因之一)
  const resonanceHistory = useMemo(
    () => (klineStart && data ? data.history.filter(h => h.date >= klineStart) : (data?.history ?? [])),
    [data, klineStart],
  )
  // 五图统一日期轴: K线 ∪ 共振历史(共振已按 klineStart 过滤, 实际 == K线日期)。
  // 各图数据范围不一致(如 515080 K线 631 天 vs 共振 453 天 vs 情绪 472 天),
  // 缩放百分比广播到不同长度数组会错位; 补零对齐后所有图缩放窗口逐日一致。
  const alignDates = useMemo(
    () => unionDates([tradeDates, resonanceHistory.map(h => h.date)]),
    [tradeDates, resonanceHistory],
  )
  const alignedKline = useMemo(
    () => alignKlineToDates(history?.kline ?? [], alignDates),
    [history, alignDates],
  )
  const alignedHistory = useMemo(
    () => alignResonanceHistoryToDates(resonanceHistory, alignDates),
    [resonanceHistory, alignDates],
  )
  const heatmapData = useMemo(
    () => (data ? { ...data, history: alignedHistory } : null),
    [data, alignedHistory],
  )

  if (error) {
    return (
      <div className="text-red-400 text-center py-20">
        <div>共振数据加载失败，请确认服务已启动</div>
        <button
          onClick={() => refetch()}
          className="mt-4 px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white"
        >
          重试
        </button>
      </div>
    )
  }
  if (isLoading || !data) {
    return <div className="text-gray-400 text-center py-20">共振数据加载中...</div>
  }

  const selectLight = (key: string) => {
    if (data?.date) setSelected({ date: data.date, indicator: key })
  }
  const selectDate = (date: string) => setSelected({ date, indicator: null })
  const selectCell = (date: string, indicator: string) => setSelected({ date, indicator })

  const handleZoom = (w: DateWindow) => {
    setDateWindow(prev => (prev && prev.start === w.start && prev.end === w.end ? prev : w))
  }

  // 切换 ETF: 重置选中日/缩放窗口(旧 ETF 日期在新数据上无意义),
  // 图表组件用 key={code} 强制重挂载, 避免 notMerge setOption 撞主流程
  const handleCodeChange = (next: string) => {
    if (next === code) return
    setSelected(null)
    setDateWindow(null)
    // 切到无 beta 的 ETF 时复位算法版本(避免 UI 与数据错位)
    if (!(strategyVersions?.[next] ?? false)) setAlgoVersion('stable')
    setCode(next)
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await refreshEtf()
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['resonance', code] }),
        queryClient.invalidateQueries({ queryKey: ['etfHistory', code] }),
        queryClient.invalidateQueries({ queryKey: ['resonanceTrades', code] }),
      ])
    } catch (e) {
      console.error('手动拉取失败:', e)
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="sticky top-0 z-30 bg-gray-950/95 backdrop-blur -mx-4 px-4 py-2 border-b border-gray-800">
        <EtfSelector
          value={code}
          onChange={handleCodeChange}
          etfList={etfList ?? []}
        />
      </div>
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <h2 className="text-lg font-bold text-white">ETF择时总览</h2>
          <p className="text-xs text-gray-500 mt-1">
            {data?.name ?? code}（{code}）× 市场情绪 · 红灯=出货/过热，绿灯=吸筹/冷清
          </p>
          {code === '159352' && (
            <p className="text-xs text-sky-500/70 mt-0.5">
              * 买卖点复用沪深300信号，价格为A500自身
            </p>
          )}
        </div>

        <div className="ml-auto" />

        <div className="flex items-center gap-1 rounded border border-gray-700 overflow-hidden" title={hasBeta ? '买卖点算法版本切换' : '该 ETF 暂无 Beta 调试版'}>
          <button
            onClick={() => setAlgoVersion('stable')}
            className={"px-3 py-1.5 text-sm transition-colors " + (algoVersion === 'stable' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200')}
          >
            正式版
          </button>
          <button
            onClick={() => hasBeta && setAlgoVersion('beta')}
            disabled={!hasBeta}
            className={"px-3 py-1.5 text-sm transition-colors " + (algoVersion === 'beta' && hasBeta ? 'bg-amber-600 text-white' : 'bg-gray-800 text-gray-400' + (hasBeta ? ' hover:text-gray-200' : '')) + (!hasBeta ? ' opacity-40 cursor-not-allowed' : '')}
          >
            Beta{!hasBeta ? '（无）' : ''}
          </button>
        </div>

        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="px-3 py-1.5 rounded text-sm bg-gray-800 text-gray-200 border border-gray-700 hover:border-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {refreshing ? '拉取中…' : '手动拉取'}
        </button>
      </div>

      <div className="bg-gray-950/95 backdrop-blur border border-gray-800 rounded-lg px-3 py-2 flex items-center gap-2 flex-wrap">
        <button
          onClick={() => stepDay(-1)}
          disabled={!canPrev}
          className="px-3 py-1.5 rounded text-sm bg-gray-800 text-gray-200 border border-gray-700 hover:border-gray-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          ← 上一日
        </button>
        <span className="text-sm font-mono text-sky-400 min-w-[92px] text-center">{displayDate || '-'}</span>
        <button
          onClick={() => stepDay(1)}
          disabled={!canNext}
          className="px-3 py-1.5 rounded text-sm bg-gray-800 text-gray-200 border border-gray-700 hover:border-gray-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          下一日 →
        </button>
        <span className="ml-auto text-[11px] text-gray-600 hidden md:inline">逐日回放练盘感（键盘 ← → 亦可）· 点选/缩放任意图表，全部联动</span>
      </div>

      {/* V1: 红绿灯面板 */}
      {data ? (
        <ResonanceLights
          data={data}
          selectedKey={selected?.date === data.date ? selected?.indicator ?? null : null}
          onSelect={selectLight}
        />
      ) : null}

      <MarketSentimentSection
        key={code}
        selectedDate={selected?.date ?? null}
        bridge={bridge}
        onSelectDate={selectDate}
        dateWindow={dateWindow}
        onZoomChange={handleZoom}
        alignDates={alignDates}
      />

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center gap-3 mb-2 flex-wrap">
          <h3 className="text-sm font-medium text-gray-300">K线走势（点击K线查看当日依据）</h3>
          <span className="text-[11px] text-gray-600">
            淡红色带=危险共振日 · 淡绿色带=机会共振日 · 蓝色虚线=当前选中日 · 副图绿柱=国家队净申购（吸筹）/红柱=净赎回（卖出） · 底部曲线=综合概率（红→黄→绿渐变，45/35 虚线为吸筹/出货线） · B/S=策略买卖点
          </span>
        </div>
        {history ? (
          <ResonanceKline
            key={code}
            kline={alignedKline}
            history={alignedHistory}
            signals={history.daily_signals}
            trades={tradesData?.trades ?? []}
            selectedDate={selected?.date ?? null}
            onSelectDate={selectDate}
            dateWindow={dateWindow}
            onZoomChange={handleZoom}
            bridge={bridge}
          />
        ) : (
          <div className="text-gray-500 text-center py-16">K线加载中...</div>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-300 mb-2">红绿灯走势（点击柱查看当日依据）</h3>
            <ResonanceChart
              key={code}
              history={alignedHistory}
              selectedDate={selected?.date ?? null}
              onSelectDate={selectDate}
              bridge={bridge}
            />
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-300 mb-2">指标状态热力图（点击单元格查看依据）</h3>
            <ResonanceHeatmap
              key={code}
              data={heatmapData!}
              selectedDate={selected?.date ?? null}
              onSelect={selectCell}
              bridge={bridge}
            />
          </div>
        </div>

      <ResonanceEvidencePanel
        code={code}
        selection={selected}
        onClose={() => setSelected(null)}
      />

      <ResonanceMethodNote />
    </div>
  )
}