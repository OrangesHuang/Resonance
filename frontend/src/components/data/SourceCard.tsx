import type { DataFlowItem } from '../../api/types'
import FlowSteps from './FlowSteps'

const LEVEL_STYLES: Record<string, string> = {
  ok: 'bg-green-500/15 text-green-400 border-green-500/30',
  warn: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  empty: 'bg-red-500/15 text-red-400 border-red-500/30',
}

interface StatLine {
  label: string
  value: string
}

interface Progress {
  current: number
  total: number
  message: string
}

export default function SourceCard({ title, description, stats, level, levelText, actionLabel, onAction, disabled, running, progress, secondaryLabel, secondaryOnAction, secondaryDisabled, secondaryRunning, flow }: {
  title: string
  description: string
  stats: StatLine[]
  level: 'ok' | 'warn' | 'empty'
  levelText: string
  actionLabel: string
  onAction: () => void
  disabled: boolean
  running: boolean
  progress?: Progress | null
  secondaryLabel?: string
  secondaryOnAction?: () => void
  secondaryDisabled?: boolean
  secondaryRunning?: boolean
  flow?: DataFlowItem[]
}) {
  const pct = progress && progress.total > 0
    ? Math.round((progress.current / progress.total) * 100)
    : null
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <span className={`px-2 py-0.5 rounded text-xs border ${LEVEL_STYLES[level]}`}>{levelText}</span>
      </div>
      <p className="text-xs text-gray-500 mb-3 leading-relaxed">{description}</p>
      <div className="space-y-1 mb-3">
        {stats.map(s => (
          <div key={s.label} className="flex items-center justify-between text-xs gap-2">
            <span className="text-gray-500 shrink-0">{s.label}</span>
            <span className="text-gray-300 font-mono truncate">{s.value}</span>
          </div>
        ))}
      </div>
      {flow && flow.length > 0 && (
        <div className="mb-3 pt-3 border-t border-gray-800/80">
          <FlowSteps flow={flow} />
        </div>
      )}
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
      <div className="mt-auto flex gap-2">
        <button
          onClick={onAction}
          disabled={disabled}
          className="flex-1 px-3 py-1.5 rounded text-sm bg-gray-800 text-gray-200 border border-gray-700 hover:border-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {running ? '进行中…' : actionLabel}
        </button>
        {secondaryLabel && secondaryOnAction && (
          <button
            onClick={secondaryOnAction}
            disabled={secondaryDisabled}
            className="flex-1 px-3 py-1.5 rounded text-sm bg-sky-500/15 text-sky-300 border border-sky-500/40 hover:border-sky-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {secondaryRunning ? '进行中…' : secondaryLabel}
          </button>
        )}
      </div>
    </div>
  )
}
