import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { fetchPortfolioBacktest } from '../api/client'

const KIND_STYLE: Record<string, string> = {
  BUY: 'text-green-400',
  TOPUP: 'text-sky-400',
  REDUCE: 'text-amber-400',
  SELL: 'text-red-400',
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
  const { data, isLoading, error } = useQuery({
    queryKey: ['portfolioBacktest'],
    queryFn: fetchPortfolioBacktest,
    staleTime: 5 * 60 * 1000,
  })

  const option = useMemo(() => {
    if (!data || data.curve.length === 0) return null
    const dates = data.curve.map(c => c.date)
    const nav = data.curve.map(c => c.nav_per_share)
    const pos = data.curve.map(c => c.position_pct)
    return {
      backgroundColor: 'transparent',
      animation: false,
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#111827',
        borderColor: '#374151',
        textStyle: { color: '#e5e7eb' },
        formatter: (params: { seriesName: string; dataIndex: number; value: number }[]) => {
          const i = params[0]?.dataIndex ?? 0
          const c = data.curve[i]
          if (!c) return ''
          return `<div style="font-size:11px;line-height:1.8">` +
            `<b>${c.date}</b><br/>` +
            `每份净值：<b style="color:#22c55e">${c.nav_per_share.toFixed(4)} 元</b><br/>` +
            `总资产：${fmtWan(c.nav)} 元<br/>` +
            `仓位：${c.position_pct.toFixed(1)}%</div>`
        },
      },
      legend: { data: ['每份净值(元)', '仓位%'], textStyle: { color: '#9ca3af' }, top: 0 },
      grid: { left: 55, right: 50, top: 30, bottom: 30 },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: '#6b7280', fontSize: 10 },
        axisLine: { lineStyle: { color: '#374151' } },
      },
      yAxis: [
        { type: 'value', scale: true, axisLabel: { color: '#6b7280' }, splitLine: { lineStyle: { color: '#1f2937' } } },
        { type: 'value', min: 0, max: 100, axisLabel: { color: '#6b7280', formatter: '{value}%' }, splitLine: { show: false } },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: 0 },
        { type: 'slider', xAxisIndex: 0, top: '88%', height: 16, borderColor: '#374151', backgroundColor: '#111827', textStyle: { color: '#6b7280' } },
      ],
      series: [
        {
          name: '每份净值(元)',
          type: 'line',
          data: nav,
          showSymbol: false,
          lineStyle: { width: 1.8, color: '#22c55e' },
          itemStyle: { color: '#22c55e' },
          areaStyle: { color: 'rgba(34, 197, 94, 0.08)' },
        },
        {
          name: '仓位%',
          type: 'line',
          yAxisIndex: 1,
          data: pos,
          showSymbol: false,
          lineStyle: { width: 1, color: '#38bdf8', type: 'dashed' as const },
          itemStyle: { color: '#38bdf8' },
        },
      ],
    }
  }, [data])

  if (isLoading) return <div className="text-gray-500 text-center py-10">组合回测加载中...</div>
  if (error || !data) return <div className="text-red-400 text-center py-10">组合回测数据加载失败</div>

  const trades = [...data.trades].reverse()

  return (
    <div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <h2 className="text-xl font-bold text-white">组合回测</h2>
        <span className="text-xs text-gray-500">
          924 后 8 标的 · 买入 12.5% / 余钱 25% / 新信号触发降仓 · 信号次日成交 · 初始 {fmtWan(data.initial_capital)} 元，每份 1 元
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-4">
        <StatCard label="累计收益" value={`+${data.total_return_pct.toFixed(1)}%`} tone="green" />
        <StatCard label="最大回撤" value={`-${data.max_drawdown_pct.toFixed(1)}%`} tone="red" />
        <StatCard label="期末每份净值" value={`${data.final_nav_per_share.toFixed(4)} 元`} sub="初始 1.0000 元" />
        <StatCard label="期末总资产" value={fmtWan(data.final_nav)} sub="初始 100 万" />
        <StatCard label="平均仓位" value={`${data.avg_position_pct.toFixed(1)}%`} sub="资金利用率" />
        <StatCard label="策略信号" value={`${data.signal_count} 笔`} sub={`${data.trades.length} 次组合操作`} />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <div className="text-xs text-gray-500 mb-2">净值走势（每份净值 · 虚线为组合仓位%）</div>
        {option && <ReactECharts option={option} style={{ height: 380 }} lazyUpdate />}
      </div>

      {data.open_positions.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 mb-4">
          <div className="text-xs text-gray-500 mb-2">当前持仓</div>
          <div className="flex flex-wrap gap-2">
            {data.open_positions.map(p => (
              <span key={p.code} className="px-2 py-1 rounded text-xs bg-gray-800 text-gray-300 border border-gray-700">
                {p.code} {p.name}
                <span className="text-amber-400 ml-1">{p.units}u</span>
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
            买入 12.5% → 加仓至 25% → 新信号时减仓至 12.5% → 卖出信号清仓
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
                  <td className="py-1.5 pr-3 text-right text-gray-400">{t.units}u</td>
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
