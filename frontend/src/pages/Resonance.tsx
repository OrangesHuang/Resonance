import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { useResonance } from '../hooks/useResonance'
import { useSentiment } from '../hooks/useSentiment'
import { fetchEtfList, fetchEtfHistory, fetchResonanceTrades } from '../api/client'
import ResonanceLights from '../components/ResonanceLights'
import ResonanceKline from '../components/ResonanceKline'
import ResonanceChart from '../components/ResonanceChart'
import ResonanceHeatmap from '../components/ResonanceHeatmap'
import ResonanceEvidencePanel, { type ResonanceSelection } from '../components/ResonanceEvidencePanel'
import ResonanceMethodNote from '../components/ResonanceMethodNote'
import SentimentLineChart from '../components/SentimentLineChart'
import { DEFAULT_VISIBLE_BARS, type DateWindow } from '../components/chartZoom'
import type { ZoneKey } from '../api/types'

const KLINE_DAYS = 640

const ZONE_TEXT: Record<ZoneKey, string> = {
  danger: 'text-red-400',
  neutral: 'text-amber-400',
  safe: 'text-green-400',
}

function MarketSentimentSection({ selectedDate, onSelectDate, dateWindow, onZoomChange, minDate }: {
  selectedDate: string | null
  onSelectDate: (date: string) => void
  dateWindow: DateWindow | null
  onZoomChange: (w: DateWindow) => void
  minDate: string | null
}) {
  const { data, isLoading, error } = useSentiment()

  if (error) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg py-6 text-center text-xs text-gray-600">
        情绪数据加载失败
      </div>
    )
  }
  if (isLoading || !data) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg py-10 text-center text-sm text-gray-500">
        情绪数据加载中...
      </div>
    )
  }

  const turnover = minDate ? data.turnover.filter(p => p.date >= minDate) : data.turnover
  const margin = minDate ? data.margin.filter(p => p.date >= minDate) : data.margin
  const dates = turnover.map(p => p.date)
  const marginByDate = new Map(margin.map(p => [p.date, p]))
  const marginLine = dates.map(d => marginByDate.get(d)?.fin_balance_yi ?? null)
  const marginBar = dates.map(d => marginByDate.get(d)?.net_fin_buy_yi ?? null)
  const cur = data.zone.current

  return (
    <div>
      <div className="flex items-center gap-3 mb-2 flex-wrap">
        <h3 className="text-sm font-medium text-gray-300">市场情绪走势（成交额热度 / 融资杠杆两灯的底层数据）</h3>
        {cur && (
          <span className="text-xs text-gray-500">
            情绪分区 <b className={ZONE_TEXT[cur.zone]}>{cur.label}</b>
            · 成交额 {cur.turnover.percentile.toFixed(0)}% 分位
            · 融资 {cur.margin.percentile.toFixed(0)}% 分位
          </span>
        )}
        <Link to="/sentiment" className="ml-auto text-xs text-gray-500 hover:text-gray-300 transition-colors">
          查看详情 →
        </Link>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-500 mb-1">两市成交额(万亿) · MA5</div>
          <SentimentLineChart
            dates={dates}
            height={240}
            yFormatter={v => (v / 10000).toFixed(4)}
            lineTip={v => `${(v / 10000).toFixed(4)} 万亿`}
            selectedDate={selectedDate}
            onSelectDate={onSelectDate}
            dateWindow={dateWindow}
            onZoomChange={onZoomChange}
            lines={[
              { name: '成交额', data: turnover.map(p => p.total_amount_yi), color: '#3b82f6', width: 1.5 },
              { name: 'MA5', data: turnover.map(p => p.ma5_yi), color: '#f59e0b', width: 1.2 },
            ]}
          />
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-500 mb-1">融资余额(万亿) · 净买入(亿)</div>
          <SentimentLineChart
            dates={dates}
            height={240}
            yFormatter={v => (v / 10000).toFixed(4)}
            lineTip={v => `${(v / 10000).toFixed(4)} 万亿`}
            barFormatter={v => v.toFixed(0)}
            selectedDate={selectedDate}
            onSelectDate={onSelectDate}
            dateWindow={dateWindow}
            onZoomChange={onZoomChange}
            lines={[
              { name: '融资余额', data: marginLine, color: '#a855f7', width: 1.5 },
            ]}
            bars={{
              name: '净买入',
              data: marginBar,
              colorFor: v => (v >= 0 ? '#ef4444' : '#22c55e'),
            }}
          />
        </div>
      </div>
    </div>
  )
}

export default function Resonance() {
  const [code, setCode] = useState('510300')
  const [selected, setSelected] = useState<ResonanceSelection | null>(null)
  const [dateWindow, setDateWindow] = useState<DateWindow | null>(null)

  const { data, isLoading, error } = useResonance(code)
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
    queryKey: ['resonanceTrades', code],
    queryFn: () => fetchResonanceTrades(code),
    staleTime: 10 * 60 * 1000,
  })

  const tradeDates = history?.kline.map(k => k.date) ?? []
  const klineStart = tradeDates[0] ?? null
  const displayDate = selected?.date ?? data?.date ?? tradeDates[tradeDates.length - 1] ?? ''
  const curIdx = displayDate ? tradeDates.indexOf(displayDate) : -1
  const canPrev = curIdx === -1 ? tradeDates.length > 1 : curIdx > 0
  const canNext = curIdx >= 0 && curIdx < tradeDates.length - 1

  const stepDay = (dir: number) => {
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
  }

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

  if (error) {
    return <div className="text-red-400 text-center py-20">共振数据加载失败，请确认服务已启动</div>
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

  const resonanceHistory = klineStart && data ? data.history.filter(h => h.date >= klineStart) : (data?.history ?? [])

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <h2 className="text-lg font-bold text-white">多指标共振</h2>
          <p className="text-xs text-gray-500 mt-1">
            {data?.name ?? code}（{code}）× 市场情绪 · 红灯=出货/过热，绿灯=吸筹/冷清
          </p>
        </div>

        <div className="ml-auto" />

        <select
          value={code}
          onChange={e => setCode(e.target.value)}
          className="bg-gray-800 border border-gray-700 text-sm text-gray-200 rounded px-3 py-1.5 focus:outline-none focus:border-gray-500"
        >
          {(etfList ?? []).map(etf => (
            <option key={etf.code} value={etf.code}>
              {etf.code} {etf.name}
            </option>
          ))}
        </select>
      </div>

      <div className="sticky top-0 z-20 bg-gray-950/95 backdrop-blur border border-gray-800 rounded-lg px-3 py-2 flex items-center gap-2 flex-wrap">
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
        <span className="ml-auto text-[11px] text-gray-600">逐日回放练盘感（键盘 ← → 亦可）· 点选/缩放任意图表，全部联动</span>
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
        selectedDate={selected?.date ?? null}
        onSelectDate={selectDate}
        dateWindow={dateWindow}
        onZoomChange={handleZoom}
        minDate={klineStart}
      />

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center gap-3 mb-2 flex-wrap">
          <h3 className="text-sm font-medium text-gray-300">K线走势（点击K线查看当日依据）</h3>
          <span className="text-[11px] text-gray-600">
            淡红色带=危险共振日 · 淡绿色带=机会共振日 · 蓝色虚线=当前选中日 · 副图绿柱=国家队净申购（吸筹）/红柱=净赎回（卖出） · 底部曲线=综合概率（70%红/50%橙分界） · 最底彩条=交易方向（绿=吸筹/红=出货/灰=中性） · B/S=策略买卖点
          </span>
        </div>
        {history ? (
          <ResonanceKline
            kline={history.kline}
            history={resonanceHistory}
            signals={history.daily_signals}
            trades={tradesData?.trades ?? []}
            selectedDate={selected?.date ?? null}
            onSelectDate={selectDate}
            dateWindow={dateWindow}
            onZoomChange={handleZoom}
          />
        ) : (
          <div className="text-gray-500 text-center py-16">K线加载中...</div>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-300 mb-2">红绿灯走势（点击柱查看当日依据）</h3>
            <ResonanceChart
              history={resonanceHistory}
              selectedDate={selected?.date ?? null}
              onSelectDate={selectDate}
              dateWindow={dateWindow}
              onZoomChange={handleZoom}
            />
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-300 mb-2">指标状态热力图（点击单元格查看依据）</h3>
            <ResonanceHeatmap
              data={{ ...data!, history: resonanceHistory }}
              selectedDate={selected?.date ?? null}
              onSelect={selectCell}
              dateWindow={dateWindow}
              onZoomChange={handleZoom}
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
