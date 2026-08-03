import { useMemo, useState } from 'react'
import { useQuery, useQueries } from '@tanstack/react-query'
import { fetchEtfList, fetchEtfHistory, fetchResonanceTrades } from '../api/client'
import CompareKline from '../components/CompareKline'
import type { TradePoint } from '../api/types'

const KLINE_DAYS = 640

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
  const [hidden, setHidden] = useState<Set<string>>(new Set())

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
        return { code, name: history.name, idx: history.idx, kline: history.kline, trades: trades.trades }
      },
      staleTime: 5 * 60 * 1000,
    })),
  })

  const cards = useMemo(
    () => results.filter(r => r.data && !hidden.has(r.data.code)).map(r => r.data!),
    [results, hidden],
  )

  const toggle = (code: string) => {
    setHidden(prev => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <h2 className="text-xl font-bold text-white">K线对比</h2>
        <span className="text-xs text-gray-500">纵向对比各 ETF 走势与策略买卖点（点击勾选显隐）</span>
      </div>

      <div className="flex items-center gap-3 mb-4 flex-wrap text-xs">
        {(etfList ?? []).map(etf => (
          <label key={etf.code} className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={!hidden.has(etf.code)}
              onChange={() => toggle(etf.code)}
              className="accent-sky-500 w-3.5 h-3.5"
            />
            <span className={hidden.has(etf.code) ? 'text-gray-600' : 'text-gray-300'}>
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
              <CompareKline kline={card.kline} trades={card.trades} />
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
