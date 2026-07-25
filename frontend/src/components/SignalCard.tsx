import type { EtfSignal } from '../api/types'

const LEVEL_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  HIGH: { bg: 'bg-red-500/20', text: 'text-red-400', label: '高确信' },
  MID: { bg: 'bg-amber-500/20', text: 'text-amber-400', label: '中等' },
  LOW: { bg: 'bg-green-500/20', text: 'text-green-400', label: '正常' },
}

export default function SignalBadge({ level }: { level: string }) {
  const style = LEVEL_STYLES[level] || LEVEL_STYLES.LOW
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  )
}

const DIRECTION_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  ACCUMULATE: { bg: 'bg-red-500/20', text: 'text-red-400', label: '吸筹' },
  DISTRIBUTE: { bg: 'bg-cyan-500/20', text: 'text-cyan-400', label: '出货' },
  NEUTRAL: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: '中性' },
}

export function DirectionBadge({ direction }: { direction?: string | null }) {
  const style = DIRECTION_STYLES[direction ?? 'NEUTRAL'] || DIRECTION_STYLES.NEUTRAL
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  )
}

export function SignalCard({ signal, onClick }: { signal: EtfSignal; onClick: () => void }) {
  const price = signal.price ?? signal.close_price ?? 0
  const changePct = signal.change_pct ?? 0
  const volumeRatio = signal.volume_ratio ?? 0
  const volProb = signal.vol_prob ?? 0
  const dirProb = signal.dir_prob ?? 0
  const compositeProb = signal.composite_prob ?? 0
  const changeColor = changePct >= 0 ? 'text-red-400' : 'text-green-400'
  const changeSign = changePct >= 0 ? '+' : ''

  return (
    <div
      onClick={onClick}
      className="bg-gray-900 border border-gray-800 rounded-lg p-4 cursor-pointer hover:border-gray-600 transition-colors"
    >
      <div className="flex items-center justify-between mb-2">
        <div>
          <span className="font-medium text-sm text-white">{signal.name}</span>
          <span className="ml-2 text-xs text-gray-500">{signal.code}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <DirectionBadge direction={signal.trade_direction} />
          <SignalBadge level={signal.signal_level} />
        </div>
      </div>

      <div className="flex items-baseline gap-3 mb-3">
        <span className="text-lg font-mono text-white">{price.toFixed(3)}</span>
        <span className={`text-sm font-mono ${changeColor}`}>
          {changeSign}{changePct.toFixed(2)}%
        </span>
        {volumeRatio > 0 && (
          <span className="text-xs text-gray-400">量比 {volumeRatio.toFixed(2)}</span>
        )}
        {signal.price_position != null && (
          <span className="text-xs text-gray-400">位置 {signal.price_position.toFixed(0)}%</span>
        )}
      </div>

      <div className="space-y-1.5">
        <FactorBar label="量能" value={volProb} color="bg-blue-500" />
        <FactorBar label="方向" value={dirProb} color="bg-purple-500" />
        <FactorBar label="份额" value={signal.share_prob ?? 0} color="bg-cyan-500" muted={signal.share_prob == null} />
      </div>

      <div className="mt-3 pt-2 border-t border-gray-800 flex items-center justify-between">
        <span className="text-xs text-gray-500">综合概率</span>
        <span className={`text-lg font-bold font-mono ${
          compositeProb >= 70 ? 'text-red-400' :
          compositeProb >= 50 ? 'text-amber-400' : 'text-green-400'
        }`}>
          {compositeProb.toFixed(1)}%
        </span>
      </div>

      {signal.premium_pct != null && (
        <div className="mt-1 text-xs text-gray-500">
          溢价率: <span className={signal.premium_pct >= 0 ? 'text-red-400' : 'text-green-400'}>
            {signal.premium_pct >= 0 ? '+' : ''}{signal.premium_pct.toFixed(3)}%
          </span>
        </div>
      )}
    </div>
  )
}

function FactorBar({ label, value, color, muted }: { label: string; value: number; color: string; muted?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 w-8">{label}</span>
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${muted ? 'bg-gray-700' : color}`}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
      <span className={`text-xs font-mono w-10 text-right ${muted ? 'text-gray-600' : 'text-gray-300'}`}>
        {muted ? '-' : `${value.toFixed(0)}%`}
      </span>
    </div>
  )
}
