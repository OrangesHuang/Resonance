import type { V2SignalsResponse, V2AnomalyVector } from '../api/types'

const REGIME_LABELS: Record<string, { text: string; cls: string }> = {
  bull:  { text: '牛市', cls: 'text-red-400 bg-red-500/10 border-red-500/30' },
  bear:  { text: '熊市', cls: 'text-green-400 bg-green-500/10 border-green-500/30' },
  range: { text: '震荡', cls: 'text-amber-400 bg-amber-500/10 border-amber-500/30' },
}

function signalColor(signal: number): string {
  if (signal > 0.3) return 'text-green-400'
  if (signal < -0.3) return 'text-red-400'
  return 'text-gray-400'
}

function signalBg(signal: number): string {
  if (signal > 0.3) return 'bg-green-500/15 border-green-500/30'
  if (signal < -0.3) return 'bg-red-500/15 border-red-500/30'
  return 'bg-gray-700/40 border-gray-700'
}

function signalBarColor(v: number): string {
  if (v > 0) return 'bg-green-500'
  if (v < 0) return 'bg-red-500'
  return 'bg-gray-600'
}

function AnomalyBar({ label, value, note }: { label: string; value: number; note: string }) {
  const pct = Math.abs(value) * 100
  const barWidth = Math.min(pct, 100)
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-16 text-gray-500 shrink-0 text-right">{label}</span>
      <div className="flex-1 h-5 bg-gray-800 rounded overflow-hidden relative">
        <div
          className={`h-full rounded transition-all ${signalBarColor(value)}`}
          style={{ width: `${barWidth}%`, marginLeft: value < 0 ? `${100 - barWidth}%` : '0%' }}
        />
        <span className="absolute inset-0 flex items-center justify-center font-mono text-[10px] text-white/80">
          {value.toFixed(2)}
        </span>
      </div>
      <span className="w-20 text-gray-600 shrink-0 truncate">{note}</span>
    </div>
  )
}

function ProbBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-14 text-gray-500 shrink-0">{label}</span>
      <div className="flex-1 h-4 bg-gray-800 rounded overflow-hidden">
        <div
          className={`h-full rounded ${color}`}
          style={{ width: `${Math.min(value * 100, 100)}%` }}
        />
      </div>
      <span className="w-10 text-right font-mono text-gray-300">{(value * 100).toFixed(0)}%</span>
    </div>
  )
}

export default function ResonanceV2Panel({ data }: { data: V2SignalsResponse }) {
  const latest = data.latest
  if (!latest) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center text-gray-500 text-sm py-8">
        V2 信号数据不足（需至少 60 个交易日）
      </div>
    )
  }

  const regime = REGIME_LABELS[data.regime_label] ?? REGIME_LABELS.range
  const sigCls = signalColor(latest.signal)
  const sigBg = signalBg(latest.signal)

  const dims: { key: keyof V2AnomalyVector; label: string; note: string }[] = [
    { key: 'vol',       label: '量能',   note: latest.anomaly.vol > 0 ? '放量' : '缩量' },
    { key: 'price',     label: '价格',   note: latest.anomaly.price > 0 ? '强势' : '弱势' },
    { key: 'share',     label: '份额',   note: latest.anomaly.share > 0 ? '净申购' : '净赎回' },
    { key: 'breadth',   label: '广度',   note: latest.anomaly.breadth > 0 ? '普涨' : '普跌' },
    { key: 'divergence', label: '背离',   note: latest.anomaly.divergence > 0 ? '逆势吸筹' : '顺势' },
  ]

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-4">
      {/* 顶部：信号强度 + 市场状态 */}
      <div className="flex items-center gap-4 flex-wrap">
        <h3 className="text-base font-bold text-white">V2 贝叶斯信号</h3>
        <span className={`px-2 py-0.5 rounded text-xs border ${regime.cls}`}>
          市场状态: {regime.text} ({data.regime.toFixed(2)})
        </span>
        <span className="text-xs text-gray-500">
          {data.code} · {latest.date} · {data.signal_count} 个交易日
        </span>
        <div className="ml-auto flex items-center gap-4">
          <div className={`px-4 py-2 rounded-lg border ${sigBg} text-center`}>
            <div className="text-[10px] text-gray-500">信号强度</div>
            <div className={`text-2xl font-bold font-mono ${sigCls}`}>
              {latest.signal > 0 ? '+' : ''}{latest.signal.toFixed(2)}
            </div>
          </div>
        </div>
      </div>

      {/* 概率条 */}
      <div className="space-y-1.5">
        <div className="text-[10px] text-gray-600 mb-1">贝叶斯后验概率</div>
        <ProbBar label="P(吸筹)" value={latest.p_accum} color="bg-green-500/60" />
        <ProbBar label="P(出货)" value={latest.p_dist} color="bg-red-500/60" />
        <ProbBar label="P(中性)" value={latest.p_neutral} color="bg-gray-500/40" />
      </div>

      {/* 5 维异常度 */}
      <div className="space-y-1.5">
        <div className="text-[10px] text-gray-600 mb-1">异常度向量（[-1, 1]，绝对值越大越异常）</div>
        {dims.map(d => (
          <AnomalyBar key={d.key} label={d.label} value={latest.anomaly[d.key]} note={d.note} />
        ))}
      </div>

      {/* 特征匹配分数 */}
      <div className="flex gap-4 text-xs">
        <div className="flex-1 bg-gray-800/50 rounded p-2">
          <span className="text-gray-500">吸筹匹配 </span>
          <span className={`font-mono ${latest.match_accum > 0.5 ? 'text-green-400' : 'text-gray-400'}`}>
            {latest.match_accum.toFixed(2)}
          </span>
        </div>
        <div className="flex-1 bg-gray-800/50 rounded p-2">
          <span className="text-gray-500">出货匹配 </span>
          <span className={`font-mono ${latest.match_dist > 0.5 ? 'text-red-400' : 'text-gray-400'}`}>
            {latest.match_dist.toFixed(2)}
          </span>
        </div>
      </div>

      <div className="text-[10px] text-gray-600">
        特征向量: 吸筹=[量+0.7 价-0.5 份+0.4 广-0.3 背离+0.8] ·
        出货=[量+0.6 价+0.5 份-0.4 广+0.3 背离-0.8] ·
        买入阈值 +{'>'}0.7 · 卖出阈值 {'<'}-0.7
      </div>
    </div>
  )
}
