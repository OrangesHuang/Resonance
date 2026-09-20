import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useResonanceScanAll } from '../hooks/useResonance'
import type { ScanAllItem, LightState } from '../api/types'

const LIGHT_DOT: Record<LightState, string> = {
  red: 'bg-red-500',
  green: 'bg-green-500',
  gray: 'bg-gray-600',
}

const SECTION_STYLES: Record<'opportunity' | 'danger' | 'neutral', { title: string; card: string; badge: string }> = {
  opportunity: {
    title: '机会共振',
    card: 'border-green-500/40 hover:border-green-400/70',
    badge: 'bg-green-500/20 text-green-400 border-green-500/40',
  },
  danger: {
    title: '危险共振',
    card: 'border-red-500/40 hover:border-red-400/70',
    badge: 'bg-red-500/20 text-red-400 border-red-500/40',
  },
  neutral: {
    title: '中性',
    card: 'border-gray-800 hover:border-gray-600',
    badge: 'bg-gray-700/40 text-gray-300 border-gray-700',
  },
}

function ScanRow({ item, kind, onClick }: { item: ScanAllItem; kind: 'opportunity' | 'danger' | 'neutral'; onClick: () => void }) {
  const s = SECTION_STYLES[kind]
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left bg-gray-900 border rounded-lg p-3 flex items-center gap-3 transition-colors ${s.card}`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-white">{item.name}</span>
          <span className="text-xs text-gray-500 font-mono">{item.code}</span>
          <span className={`px-2 py-0.5 rounded-full text-[11px] border ${s.badge}`}>{item.verdict}</span>
        </div>
        <div className="mt-1.5 flex items-center gap-1.5">
          {item.indicators.map(ind => (
            <span
              key={ind.key}
              title={`${ind.name}: ${ind.display}`}
              className={`w-2.5 h-2.5 rounded-full ${LIGHT_DOT[ind.state]}`}
            />
          ))}
          <span className="ml-2 text-[11px] text-gray-500">
            <span className="text-red-400 font-mono">{item.red_count}</span>红 ·
            <span className="text-green-400 font-mono"> {item.green_count}</span>绿 ·
            <span className="text-gray-500 font-mono"> {item.gray_count}</span>灰
          </span>
        </div>
      </div>
      <span className="shrink-0 text-[11px] text-gray-600">查看详情 ›</span>
    </button>
  )
}

function Section({ kind, items, onSelect }: {
  kind: 'opportunity' | 'danger' | 'neutral'
  items: ScanAllItem[]
  onSelect: (code: string) => void
}) {
  const s = SECTION_STYLES[kind]
  if (items.length === 0) {
    return (
      <div>
        <div className="text-xs text-gray-500 mb-2">{s.title}（0）</div>
        <div className="text-sm text-gray-600 py-3">暂无标的触发{s.title}</div>
      </div>
    )
  }
  return (
    <div>
      <div className="text-xs text-gray-500 mb-2">{s.title}（{items.length}）</div>
      <div className="space-y-2">
        {items.map(item => (
          <ScanRow key={item.code} item={item} kind={kind} onClick={() => onSelect(item.code)} />
        ))}
      </div>
    </div>
  )
}

function filterItems(items: ScanAllItem[], q: string): ScanAllItem[] {
  if (!q) return items
  return items.filter(item => item.code.includes(q) || item.name.toLowerCase().includes(q))
}

export default function ResonanceScanAll() {
  const { data, isLoading, error, refetch } = useResonanceScanAll()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  const goDetail = (code: string) => navigate(`/resonance?code=${code}`)

  if (error) {
    return (
      <div className="text-red-400 text-center py-20">
        <div>轮动扫描数据加载失败，请确认服务已启动</div>
        <button
          onClick={() => refetch()}
          className="mt-4 px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white"
        >
          重试
        </button>
      </div>
    )
  }
  if (isLoading || !data) {
    return <div className="text-gray-400 text-center py-20">轮动扫描数据加载中...</div>
  }

  const q = query.trim().toLowerCase()
  const opportunity = filterItems(data.opportunity_resonance, q)
  const danger = filterItems(data.danger_resonance, q)
  const neutral = filterItems(data.neutral, q)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <h2 className="text-lg font-bold text-white">ETF轮动扫描</h2>
          <p className="text-xs text-gray-500 mt-1">
            全部 {data.total} 只 ETF × 五灯共振 · 数据日期 {data.date ?? '-'} · 红灯=出货/过热，绿灯=吸筹/冷清
          </p>
        </div>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="搜索代码/名称…"
          className="ml-auto px-2.5 py-1.5 rounded text-xs bg-gray-800 text-gray-200 w-48
                     border border-gray-700 focus:outline-none focus:border-sky-500 placeholder:text-gray-600"
        />
      </div>

      <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-4 space-y-6">
        <Section kind="opportunity" items={opportunity} onSelect={goDetail} />
        <Section kind="danger" items={danger} onSelect={goDetail} />
        <Section kind="neutral" items={neutral} onSelect={goDetail} />
      </div>
    </div>
  )
}
