import { useResonanceDay } from '../hooks/useResonance'
import EvidenceCard from './EvidenceCard'

const VERDICT_STYLES: Record<string, string> = {
  危险共振: 'bg-red-500/20 text-red-400 border-red-500/40',
  机会共振: 'bg-green-500/20 text-green-400 border-green-500/40',
  中性: 'bg-gray-700/40 text-gray-300 border-gray-700',
}

export interface ResonanceSelection {
  date: string
  indicator: string | null
}

export default function ResonanceEvidencePanel({ code, selection, onClose }: {
  code: string
  selection: ResonanceSelection | null
  onClose: () => void
}) {
  const { data, isFetching } = useResonanceDay(code, selection?.date ?? null)
  const current = selection && data && data.date === selection.date ? data : null

  if (!selection) {
    return (
      <div className="bg-gray-900/40 border border-dashed border-gray-800 rounded-lg p-6 text-center text-sm text-gray-500 leading-relaxed">
        点击任意指示灯、走势图柱或热力图单元格，在此查看该日各指标的判定依据
        <span className="block text-xs text-gray-600 mt-1">指标值 · 计算方法 · 当日算式 · 原始数据 · 判定理由</span>
      </div>
    )
  }

  return (
    <div className="bg-gray-950 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center gap-3 flex-wrap mb-4">
        <h3 className="text-base font-bold text-white">归因详情</h3>
        <span className="text-sm text-gray-400 font-mono">{selection.date}</span>
        {current && (
          <>
            <span className="text-xs text-gray-400">
              <span className="text-red-400 font-mono font-bold">{current.red_count}</span> 红 ·
              <span className="text-green-400 font-mono font-bold"> {current.green_count}</span> 绿 ·
              <span className="text-gray-500 font-mono"> {current.gray_count}</span> 灰
            </span>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${VERDICT_STYLES[current.verdict] ?? VERDICT_STYLES['中性']}`}>
              {current.verdict}
            </span>
          </>
        )}
        {isFetching && !current && <span className="text-xs text-gray-500">加载归因数据中…</span>}
        <button
          type="button"
          onClick={onClose}
          className="ml-auto text-xs text-gray-500 hover:text-gray-300 px-2 py-1 rounded border border-gray-700 transition-colors"
        >
          收起 ✕
        </button>
      </div>

      {current ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {current.indicators.map(ind => (
            <EvidenceCard
              key={ind.key}
              ind={ind}
              highlight={selection.indicator === ind.key}
            />
          ))}
        </div>
      ) : (
        <div className="text-gray-500 text-center py-10 text-sm">
          {isFetching ? '加载归因数据中...' : '暂无该日数据'}
        </div>
      )}
    </div>
  )
}
