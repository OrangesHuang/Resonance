import type { TradePoint, DailySignal, KlinePoint } from '../../api/types'

const DIR_LABELS: Record<string, string> = {
  ACCUMULATE: '吸筹',
  DISTRIBUTE: '出货',
  NEUTRAL: '中性',
}

function fmt(v: number | null | undefined, digits = 2, suffix = ''): string {
  if (v == null) return '-'
  return `${v.toFixed(digits)}${suffix}`
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

export default function TradeReasonPanel({ trade, signal, kline, onClose }: {
  trade: TradePoint
  signal: DailySignal | undefined
  kline: KlinePoint | undefined
  onClose: () => void
}) {
  const isBuy = trade.action === 'BUY'
  const accent = isBuy ? 'text-green-400' : 'text-red-400'
  const dir = signal?.trade_direction ?? 'NEUTRAL'
  const cp = signal?.composite_prob
  const cpTone = cp == null ? 'flat' : cp >= 45 ? 'up' : cp <= 35 ? 'down' : 'flat'
  const flow = signal?.shares_delta_yi
  const flowTone = flow == null ? 'flat' : flow >= 0 ? 'up' : 'down'
  const chg = kline ? (kline.close / kline.open - 1) * 100 : null

  return (
    <div className="mt-2 bg-gray-900/70 border border-gray-800 rounded-lg px-3 py-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-300">
          <span className={`font-bold ${accent}`}>{isBuy ? '◆ 买入' : '▼ 卖出'}</span>
          <span className="font-mono text-gray-200"> {trade.date} @ {trade.price}</span>
        </span>
        <button onClick={onClose} className="text-gray-600 hover:text-gray-300 text-xs transition-colors">× 收起</button>
      </div>

      <div className="text-xs text-gray-400 mb-2 leading-relaxed">{trade.reason}</div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6">
        <div>
          <Row label="涨跌幅" value={chg == null ? '-' : `${chg >= 0 ? '+' : ''}${chg.toFixed(1)}%`} tone={chg == null ? 'flat' : chg >= 0 ? 'up' : 'down'} />
          <Row label="量比" value={fmt(signal?.volume_ratio)} />
          <Row label="价格位置" value={fmt(signal?.price_position, 0, '%')} tone={signal?.price_position != null && signal.price_position >= 70 ? 'down' : signal?.price_position != null && signal.price_position <= 30 ? 'up' : 'flat'} />
        </div>
        <div>
          <Row label="份额净申赎" value={flow == null ? '-' : `${flow >= 0 ? '+' : ''}${flow.toFixed(2)} 亿份`} tone={flowTone} />
          <Row label="份额信号" value={fmt(signal?.share_prob, 0)} />
          <Row label="方向" value={DIR_LABELS[dir] ?? '-'} tone={dir === 'ACCUMULATE' ? 'up' : dir === 'DISTRIBUTE' ? 'down' : 'flat'} />
        </div>
        <div>
          <Row label="综合概率" value={fmt(cp, 1, '%')} tone={cpTone} />
          <Row label="信号等级" value={signal?.signal_level ?? '-'} />
        </div>
        <div className="text-gray-600 self-center text-xs leading-relaxed">
          {isBuy
            ? '低吸/恐慌路径：量能+位置+份额证据见左侧'
            : '出货/止盈路径：出货形态+份额流出确认，见左侧'}
        </div>
      </div>
    </div>
  )
}
