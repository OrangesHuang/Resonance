import type { ResonanceOverview, ResonanceIndicator, LightState } from '../api/types'

const LIGHT_STYLES: Record<LightState, { dot: string; card: string; text: string }> = {
  red: { dot: 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.7)]', card: 'border-red-500/40', text: 'text-red-400' },
  green: { dot: 'bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.7)]', card: 'border-green-500/40', text: 'text-green-400' },
  gray: { dot: 'bg-gray-600', card: 'border-gray-800', text: 'text-gray-400' },
}

const STATE_LABEL: Record<LightState, string> = { red: '风险', green: '机会', gray: '中性' }

const VERDICT_STYLES: Record<string, string> = {
  危险共振: 'bg-red-500/20 text-red-400 border-red-500/40',
  机会共振: 'bg-green-500/20 text-green-400 border-green-500/40',
  中性: 'bg-gray-700/40 text-gray-300 border-gray-700',
}

function LightCard({ ind, selected, onSelect }: {
  ind: ResonanceIndicator
  selected: boolean
  onSelect: (key: string) => void
}) {
  const s = LIGHT_STYLES[ind.state]
  return (
    <button
      type="button"
      onClick={() => onSelect(ind.key)}
      className={`w-full text-left bg-gray-900 border rounded-lg p-3 flex items-center gap-3 cursor-pointer transition-shadow hover:ring-1 hover:ring-gray-500 ${s.card} ${
        selected ? 'ring-2 ring-sky-500' : ''
      }`}
    >
      <span className={`shrink-0 w-3.5 h-3.5 rounded-full ${s.dot}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-300">{ind.name}</span>
          <span className={`text-xs ${s.text}`}>{STATE_LABEL[ind.state]}</span>
        </div>
        <div className="mt-0.5 flex items-baseline gap-2">
          <span className={`text-base font-mono ${s.text}`}>{ind.display}</span>
          <span className="text-[10px] text-gray-600 truncate">{ind.note}</span>
        </div>
      </div>
      <span className="shrink-0 text-[10px] text-gray-600">依据 ›</span>
    </button>
  )
}

function LightGroup({ title, items, selectedKey, onSelect }: {
  title: string
  items: ResonanceIndicator[]
  selectedKey: string | null
  onSelect: (key: string) => void
}) {
  if (items.length === 0) return null
  return (
    <div>
      <div className="text-xs text-gray-500 mb-2">{title}</div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {items.map(ind => (
          <LightCard
            key={ind.key}
            ind={ind}
            selected={selectedKey === ind.key}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  )
}

export default function ResonanceLights({ data, selectedKey, onSelect }: {
  data: ResonanceOverview
  selectedKey: string | null
  onSelect: (key: string) => void
}) {
  const etfLights = data.indicators.filter(i => i.group === 'etf')
  const marketLights = data.indicators.filter(i => i.group === 'market')
  const verdictCls = VERDICT_STYLES[data.verdict] ?? VERDICT_STYLES['中性']

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center gap-3 flex-wrap mb-4">
        <h3 className="text-base font-bold text-white">多指标共振</h3>
        <span className="text-xs text-gray-500">{data.name} × 市场情绪 · {data.date}</span>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-gray-400">
            <span className="text-red-400 font-mono font-bold">{data.red_count}</span> 红 ·
            <span className="text-green-400 font-mono font-bold"> {data.green_count}</span> 绿 ·
            <span className="text-gray-500 font-mono"> {data.gray_count}</span> 灰
          </span>
          <span className={`px-3 py-1 rounded-full text-sm font-bold border ${verdictCls}`}>
            {data.verdict}
          </span>
        </div>
      </div>
      <div className="space-y-4">
        <LightGroup title={`${data.name}（${data.code}）`} items={etfLights} selectedKey={selectedKey} onSelect={onSelect} />
        <LightGroup title="市场情绪整体" items={marketLights} selectedKey={selectedKey} onSelect={onSelect} />
      </div>
      <div className="mt-3 text-[11px] text-gray-600">点击任意指示灯，或点击下方走势图/热力图中的某一天，查看该日各指标的判定依据。</div>
    </div>
  )
}
