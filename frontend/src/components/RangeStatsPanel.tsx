import type { RangeStats } from './rangeStats'

function fmtPct(v: number): string {
  const s = v >= 0 ? '+' : ''
  return `${s}${v.toFixed(1)}%`
}

function Row({ label, value, tone }: { label: string; value: string; tone?: 'up' | 'down' | 'flat' }) {
  const color = tone === 'up' ? 'text-red-400' : tone === 'down' ? 'text-green-400' : 'text-gray-300'
  return (
    <div className="flex items-center justify-between text-xs py-0.5">
      <span className="text-gray-500">{label}</span>
      <span className={`font-mono ${color}`}>{value}</span>
    </div>
  )
}

export default function RangeStatsPanel({ stats, onClear }: {
  stats: RangeStats
  onClear: () => void
}) {
  const tone = stats.change_pct >= 0 ? 'up' : 'down'
  const tradeTone = stats.range_return_pct == null ? 'flat'
    : stats.range_return_pct >= 0 ? 'up' : 'down'
  return (
    <div className="mt-2 bg-gray-900/60 border border-gray-800 rounded-lg px-3 py-2 text-xs">
      <div className="flex items-center justify-between mb-1">
        <span className="text-gray-400">
          区间统计 · <span className="font-mono text-gray-200">{stats.start}</span> ~ <span className="font-mono text-gray-200">{stats.end}</span>
        </span>
        <button onClick={onClear} className="text-gray-600 hover:text-gray-300 transition-colors">× 清除</button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6">
        <div>
          <Row label="首日收盘" value={stats.start_close.toFixed(3)} />
          <Row label="末日收盘" value={stats.end_close.toFixed(3)} />
          <Row label="涨跌幅" value={fmtPct(stats.change_pct)} tone={tone} />
        </div>
        <div>
          <Row label="区间最高" value={`${stats.high.toFixed(3)} (${stats.high_date})`} />
          <Row label="区间最低" value={`${stats.low.toFixed(3)} (${stats.low_date})`} />
          <Row label="振幅" value={fmtPct(stats.amplitude_pct)} />
        </div>
        <div>
          <Row label="区间买点" value={`${stats.buy_count} 个`} tone={stats.buy_count > 0 ? 'up' : 'flat'} />
          <Row label="区间卖点" value={`${stats.sell_count} 个`} tone={stats.sell_count > 0 ? 'down' : 'flat'} />
          <Row label="区间策略收益" value={stats.range_return_pct == null ? '—' : fmtPct(stats.range_return_pct)} tone={tradeTone} />
        </div>
        <div>
          <Row label="区间累计净申赎" value={stats.net_flow_yi == null ? '—' : `${stats.net_flow_yi >= 0 ? '+' : ''}${stats.net_flow_yi.toFixed(2)} 亿份`}
            tone={stats.net_flow_yi == null ? 'flat' : stats.net_flow_yi >= 0 ? 'up' : 'down'} />
          <Row label="有效净申赎天数" value={`${stats.flow_days} 天`} />
          <div className="text-gray-600">
            {stats.net_flow_yi == null
              ? '该区间无份额数据'
              : stats.net_flow_yi >= 0
                ? '净申购 → 主力吸筹'
                : '净赎回 → 主力流出'}
          </div>
        </div>
        <div className="text-gray-600 self-center">
          {stats.open_position
            ? '区间末持仓中(按末日收盘计)'
            : stats.sell_count > 0 ? '区间末空仓' : '区间内无完整交易'}
        </div>
      </div>
    </div>
  )
}
