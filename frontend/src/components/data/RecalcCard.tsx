import FlowSteps from './FlowSteps'
import type { DataFlowItem } from '../../api/types'

interface Progress {
  current: number
  total: number
  message: string
}

export default function RecalcCard({ flow, onAction, disabled, running, progress }: {
  flow?: DataFlowItem[]
  onAction: () => void
  disabled: boolean
  running: boolean
  progress?: Progress | null
}) {
  const pct = progress && progress.total > 0
    ? Math.round((progress.current / progress.total) * 100)
    : null
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-sm font-semibold text-white">重算吸筹/出货信号</h3>
        <span className="px-2 py-0.5 rounded text-xs border bg-amber-500/15 text-amber-400 border-amber-500/30">V2对齐</span>
      </div>
      <p className="text-xs text-gray-500 mb-3 leading-relaxed">
        算法升级或大范围补份额后，将存量 composite_prob / signal_level 重算为当前 V2 四层门控口径（幂等，可重复执行）
      </p>
      {running && progress && (
        <div className="mb-3">
          <div className="h-1.5 bg-gray-800 rounded overflow-hidden">
            {pct !== null
              ? <div className="h-full bg-sky-500 transition-all" style={{ width: `${pct}%` }} />
              : <div className="h-full w-1/3 bg-sky-500 animate-pulse" />}
          </div>
          <div className="mt-1 text-xs text-gray-500 truncate">
            {progress.message}{progress.total > 0 ? ` (${progress.current}/${progress.total})` : ''}
          </div>
        </div>
      )}
      <div className="mt-auto">
        {flow && flow.length > 0 && (
          <div className="mb-3 pt-3 border-t border-gray-800/80">
            <FlowSteps flow={flow} />
          </div>
        )}
        <button
          onClick={onAction}
          disabled={disabled}
          className="w-full px-3 py-1.5 rounded text-sm bg-amber-500/15 text-amber-300 border border-amber-500/40 hover:border-amber-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {running ? '重算中…' : '重算吸筹/出货信号'}
        </button>
      </div>
    </div>
  )
}
