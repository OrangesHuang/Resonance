import { useCallback, useMemo, useRef } from 'react'
import { useQuery, useQueries } from '@tanstack/react-query'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { fetchEtfList, fetchEtfHistory, fetchResonanceTrades } from '../api/client'
import CompareKline from '../components/kline/CompareKline'
import type { ZoomRange } from '../components/kline/CompareKline'
import type { TradePoint } from '../api/types'
import { usePinnedEtfs } from '../hooks/usePinnedEtfs'

const KLINE_DAYS = 640
// 原生联动组: echarts.connect 让同组图在同一渲染批次内同步 dataZoom,
// 相比手动 dispatchAction 转发(事后异步)能真正做到"一起滚动"
const CHART_GROUP = 'klineCompare'

function calcSummary(trades: TradePoint[]) {
  let buy: { price: number; date: string } | null = null
  const rounds: number[] = []
  for (const t of trades) {
    if (t.action === 'BUY') {
      buy = { price: t.price, date: t.date }
    } else if (t.action === 'SELL' && buy) {
      rounds.push((t.price / buy.price - 1) * 100)
      buy = null
    }
  }
  let total = 1
  let wins = 0
  for (const r of rounds) {
    total *= 1 + r / 100
    if (r > 0) wins++
  }
  return {
    roundCount: rounds.length,
    winRate: rounds.length ? Math.round((wins / rounds.length) * 100) : null,
    totalPct: rounds.length ? (total - 1) * 100 : null,
    holding: buy !== null,
  }
}

export default function KlineCompare() {
  const { pinned, togglePin } = usePinnedEtfs()
  // zoomRef: 新挂载的图用当前全局缩放对齐(connect 只管已挂载图之间的实时联动)
  const zoomRef = useRef<ZoomRange>({ start: 0, end: 100 })

  const registerChart = useCallback((inst: ECharts) => {
    inst.group = CHART_GROUP
    echarts.connect(CHART_GROUP)
    const z = zoomRef.current
    inst.dispatchAction({ type: 'dataZoom', start: z.start, end: z.end }, { silent: true })
  }, [])

  // 仅记录全局缩放供新图对齐; 实时联动由 connect 原生完成, 不再手动转发
  const handleZoomChange = useCallback((z: ZoomRange) => {
    zoomRef.current = z
  }, [])

  const { data: etfList } = useQuery({
    queryKey: ['etfList'],
    queryFn: fetchEtfList,
    staleTime: Infinity,
  })

  const codes = etfList?.map(e => e.code) ?? []
  const results = useQueries({
    queries: codes.map(code => ({
      queryKey: ['klineCompare', code],
      queryFn: async () => {
        const [history, trades] = await Promise.all([
          fetchEtfHistory(code, KLINE_DAYS),
          fetchResonanceTrades(code),
        ])
        return { code, name: history.name, idx: history.idx, kline: history.kline, signals: history.daily_signals, trades: trades.trades }
      },
      staleTime: 5 * 60 * 1000,
    })),
  })

  const cards = useMemo(
    () => results.filter(r => r.data && pinned.includes(r.data.code)).map(r => r.data!),
    [results, pinned],
  )

  const sharedDates = useMemo(() => {
    const set = new Set<string>()
    for (const c of cards) for (const k of c.kline) set.add(k.date)
    return Array.from(set).sort()
  }, [cards])

  return (
    <div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <h2 className="text-xl font-bold text-white">ETF走势对比</h2>
        <span className="text-xs text-gray-500">纵向对比各 ETF 走势与策略买卖点（勾选即收藏，共振/流向页同步）</span>
      </div>

      <div className="flex items-center gap-3 mb-4 flex-wrap text-xs">
        {(etfList ?? []).map(etf => (
          <label key={etf.code} className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={pinned.includes(etf.code)}
              onChange={() => togglePin(etf.code)}
              className="accent-sky-500 w-3.5 h-3.5"
            />
            <span className={pinned.includes(etf.code) ? 'text-gray-300' : 'text-gray-600'}>
              {etf.code} {etf.name}
            </span>
          </label>
        ))}
      </div>

      <div className="space-y-6">
        {cards.map(card => {
          const s = calcSummary(card.trades)
          return (
            <div key={card.code} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <div className="flex items-center gap-3 mb-1 flex-wrap">
                <h3 className="text-sm font-semibold text-white">
                  {card.code} {card.name}
                  <span className="ml-2 text-xs text-gray-500 font-normal">（{card.idx}）</span>
                </h3>
                {s.roundCount > 0 && (
                  <span className="text-[11px] text-gray-400">
                    {s.roundCount} 轮
                    {s.totalPct != null && (
                      <span className={s.totalPct >= 0 ? 'text-green-400 ml-1.5' : 'text-red-400 ml-1.5'}>
                        累计 {s.totalPct >= 0 ? '+' : ''}{s.totalPct.toFixed(1)}%
                      </span>
                    )}
                    {s.winRate != null && <span className="ml-1.5">胜率 {s.winRate}%</span>}
                    {s.holding && <span className="text-amber-400 ml-1.5">持仓中</span>}
                  </span>
                )}
              </div>
              <CompareKline key={card.code} kline={card.kline} trades={card.trades} signals={card.signals} sharedDates={sharedDates}
                onZoomChange={handleZoomChange}
                onRegister={registerChart} />
            </div>
          )
        })}
      </div>

      {cards.length === 0 && (
        <div className="text-gray-500 text-center py-16">未选择任何 ETF</div>
      )}
    </div>
  )
}
