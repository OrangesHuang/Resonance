import type { JobState } from '../../api/types'

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
  running: 'bg-sky-500/15 text-sky-400 border-sky-500/30',
  success: 'bg-green-500/15 text-green-400 border-green-500/30',
  failed: 'bg-red-500/15 text-red-400 border-red-500/30',
}

const STATUS_TEXT: Record<string, string> = {
  pending: '排队',
  running: '运行中',
  success: '完成',
  failed: '失败',
}

function fmtTime(t: string | null): string {
  return t ? t.replace('T', ' ') : '—'
}

export default function JobsPanel({ jobs, labelOf }: { jobs: JobState[]; labelOf: (task: string) => string }) {
  if (jobs.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg py-6 text-center text-xs text-gray-600">
        暂无任务记录
      </div>
    )
  }
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800/60">
      {jobs.map(j => {
        const pct = j.total > 0 ? Math.round((j.current / j.total) * 100) : null
        const active = j.status === 'running' || j.status === 'pending'
        return (
          <div key={j.id} className="p-3">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-200">{labelOf(j.task)}</span>
              <span className={`px-2 py-0.5 rounded text-xs border ${STATUS_STYLES[j.status]}`}>
                {STATUS_TEXT[j.status]}
              </span>
              <span className="ml-auto text-xs text-gray-600 font-mono">{fmtTime(j.started_at)}</span>
            </div>
            {active && (
              <div className="mt-2 h-1.5 bg-gray-800 rounded overflow-hidden">
                {pct !== null
                  ? <div className="h-full bg-sky-500 transition-all" style={{ width: `${pct}%` }} />
                  : <div className="h-full w-1/3 bg-sky-500 animate-pulse" />}
              </div>
            )}
            <div className="mt-1 text-xs text-gray-500 truncate">
              {j.message}{j.total > 0 ? ` (${j.current}/${j.total})` : ''}
            </div>
            {j.error && <div className="mt-1 text-xs text-red-400">{j.error}</div>}
          </div>
        )
      })}
    </div>
  )
}
