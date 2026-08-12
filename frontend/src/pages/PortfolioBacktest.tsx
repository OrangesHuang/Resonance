import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchPortfolioBacktest } from '../api/client'
import type { PortfolioTrade } from '../api/types'
import { usePinnedEtfs } from '../hooks/usePinnedEtfs'
import { toRows } from '../components/portfolio/TradePopups'
import type { TradeRow } from '../components/portfolio/TradePopups'
import PortfolioChart from '../components/portfolio/PortfolioChart'

const KIND_STYLE: Record<string, string> = {
  BUY: 'text-green-400',
  SELL: 'text-red-400',
  TRIM: 'text-amber-400',
  REFILL: 'text-sky-400',
}

function fmtWan(v: number): string {
  return `${(v / 10000).toFixed(1)} 万`
}

function StatCard({ label, value, sub, tone }: {
  label: string
  value: string
  sub?: string
  tone?: 'green' | 'red' | 'gray'
}) {
  const color = tone === 'green' ? 'text-green-400'
    : tone === 'red' ? 'text-red-400' : 'text-white'
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value}</div>
      {sub && <div className="text-[11px] text-gray-500 mt-0.5">{sub}</div>}
    </div>
  )
}

export default function PortfolioBacktest() {
  const { pinned: pinnedCodes } = usePinnedEtfs()
  const { data, isLoading, error } = useQuery({
    queryKey: ['portfolioBacktest', pinnedCodes],
    queryFn: () => fetchPortfolioBacktest(pinnedCodes),
    staleTime: 5 * 60 * 1000,
  })

  // 每日交易行(图表 tooltip / 弹窗 / 表格共用)
  const displayRowsByDate = useMemo(() => {
    const m = new Map<string, TradeRow[]>()
    if (!data) return m
    const byDate = new Map<string, PortfolioTrade[]>()
    for (const t of data.trades) {
      const arr = byDate.get(t.date) ?? []
      arr.push(t)
      byDate.set(t.date, arr)
    }
    for (const [d, arr] of byDate) m.set(d, toRows(arr))
    return m
  }, [data])

  const trades = useMemo(() => {
    const out: TradeRow[] = []
    for (const d of [...displayRowsByDate.keys()].sort().reverse()) {
      out.push(...(displayRowsByDate.get(d) ?? []))
    }
    return out
  }, [displayRowsByDate])

  if (isLoading) return <div className="text-gray-500 text-center py-10">组合回测加载中...</div>
  if (error || !data) return <div className="text-red-400 text-center py-10">ETF组合回测数据加载失败</div>

  return (
    <div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <h2 className="text-xl font-bold text-white">ETF组合回测</h2>
        <span className="text-xs text-gray-500">
          收藏标的组合 · 新买点等权满仓 / 卖点整仓清仓资金待命 · 信号次日成交 · 初始 {fmtWan(data.initial_capital)} 元
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-4">
        <StatCard label="累计收益" value={`+${data.total_return_pct.toFixed(1)}%`} tone="green" />
        <StatCard label="最大回撤" value={`-${data.max_drawdown_pct.toFixed(1)}%`} tone="red" />
        <StatCard label="期末每份净值" value={`${data.final_nav_per_share.toFixed(4)} 元`} sub="初始 1.0000 元" />
        <StatCard label="期末总资产" value={fmtWan(data.final_nav)} sub="初始 100 万" />
        <StatCard label="空仓日期" value={`${data.empty_days} 个交易日`} sub={`本轮周期空仓占比 ${data.empty_days_pct.toFixed(1)}%`} />
        <StatCard label="策略信号" value={`${data.signal_count} 笔`} sub={`${data.trades.length} 次组合操作`} />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <div className="text-xs text-gray-500 mb-2">
          上: 组合每份净值 + 仓位%(虚线) · 中: ETF 净值(归一化) + B/S 买卖点 · 下: ETF 份额净申赎(红申购/绿赎回) · 三图联动缩放 · 点击圆点查看交易
        </div>
        <PortfolioChart data={data} displayRowsByDate={displayRowsByDate} />
      </div>

      {data.open_positions.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 mb-4">
          <div className="text-xs text-gray-500 mb-2">当前持仓</div>
          <div className="flex flex-wrap gap-2">
            {data.open_positions.map(p => (
              <span key={p.code} className="px-2 py-1 rounded text-xs bg-gray-800 text-gray-300 border border-gray-700">
                {p.code} {p.name}
                <span className="text-amber-400 ml-1">{p.weight_pct.toFixed(1)}%</span>
                <span className="text-gray-500 ml-1">{fmtWan(p.market_value)}</span>
                <span className="text-gray-600 ml-1">@{p.buy_date} 起</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs text-gray-500">交易记录留存（共 {trades.length} 条）</div>
          <div className="text-[11px] text-gray-600">
            新买点等权分配(减仓→建仓→补仓) → 卖点整仓清仓资金待命
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-1.5 pr-3">成交日</th>
                <th className="text-left py-1.5 pr-3">信号日</th>
                <th className="text-left py-1.5 pr-3">标的</th>
                <th className="text-left py-1.5 pr-3">操作</th>
                <th className="text-right py-1.5 pr-3">仓位</th>
                <th className="text-right py-1.5 pr-3">价格</th>
                <th className="text-right py-1.5">金额(元)</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t, i) => (
                <tr key={`${t.date}-${t.code}-${t.kind}-${i}`} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-1.5 pr-3 text-gray-400 font-mono">{t.date}</td>
                  <td className="py-1.5 pr-3 text-gray-600 font-mono">{t.signal_date || '—'}</td>
                  <td className="py-1.5 pr-3 text-gray-300">{t.code} {t.name}</td>
                  <td className={`py-1.5 pr-3 ${KIND_STYLE[t.kind] ?? ''}`}>{t.kind_label}</td>
                  <td className="py-1.5 pr-3 text-right text-gray-400">{t.weight_pct.toFixed(1)}%</td>
                  <td className="py-1.5 pr-3 text-right text-gray-400 font-mono">{t.price}</td>
                  <td className="py-1.5 text-right text-gray-300 font-mono">{(t.amount / 10000).toFixed(2)} 万</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
