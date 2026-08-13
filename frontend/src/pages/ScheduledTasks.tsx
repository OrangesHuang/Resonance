import { useEffect, useState } from 'react'
import { useScheduledTasks } from '../hooks/useData'
import type { DataFlowStep, ScheduledTaskInfo } from '../api/types'

const STEP_BADGE: Record<DataFlowStep, { label: string; cls: string }> = {
  fetch: { label: '拉取', cls: 'text-cyan-400 bg-cyan-400/10' },
  derive: { label: '加工', cls: 'text-violet-400 bg-violet-400/10' },
  write: { label: '写库', cls: 'text-emerald-400 bg-emerald-400/10' },
  read: { label: '读库', cls: 'text-blue-400 bg-blue-400/10' },
  offline: { label: '离线', cls: 'text-gray-400 bg-gray-400/10' },
  delete: { label: '清理', cls: 'text-red-400 bg-red-400/10' },
}

function fmtNextRun(iso: string | null): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').split('+')[0].slice(5, 19)
}

function fmtCountdown(ms: number): string {
  if (ms <= 0) return '即将运行'
  const total = Math.floor(ms / 1000)
  const d = Math.floor(total / 86400)
  const h = Math.floor((total % 86400) / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return d > 0 ? `${d}天 ${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(h)}:${pad(m)}:${pad(s)}`
}

function TaskCard({ task, now }: { task: ScheduledTaskInfo; now: number }) {
  const nextMs = task.next_run ? new Date(task.next_run).getTime() : null
  const prevMs = task.prev_run ? new Date(task.prev_run).getTime() : null
  const imminent = nextMs !== null && nextMs - now <= 0
  const pct =
    nextMs !== null && prevMs !== null && nextMs > prevMs
      ? Math.min(100, Math.max(0, ((now - prevMs) / (nextMs - prevMs)) * 100))
      : null
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-white">{task.label}</h3>
        <span className="shrink-0 text-[11px] text-gray-400 bg-gray-800 rounded px-2 py-0.5">
          {task.schedule}
        </span>
      </div>

      <div className="flex items-baseline justify-between gap-2">
        {nextMs !== null ? (
          <>
            <span
              className={`font-mono text-xl tabular-nums ${
                imminent ? 'text-amber-400' : 'text-gray-100'
              }`}
            >
              {fmtCountdown(nextMs - now)}
            </span>
            <span className="text-[11px] text-gray-500 font-mono">
              下次 {fmtNextRun(task.next_run)}
            </span>
          </>
        ) : (
          <span className="text-xs text-gray-600">调度器未注册</span>
        )}
      </div>

      {pct !== null && (
        <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-[width] duration-1000 ease-linear ${
              pct >= 90 ? 'bg-amber-400' : 'bg-cyan-500'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      <p className="text-xs text-gray-400 leading-relaxed">{task.purpose}</p>

      <div className="mt-auto pt-2 border-t border-gray-800 space-y-1.5">
        {task.data_flow.map((f, i) => {
          const badge = STEP_BADGE[f.step] ?? STEP_BADGE.offline
          return (
            <div key={i} className="flex items-start gap-2 text-[11px]">
              <span className={`shrink-0 rounded px-1.5 py-0.5 font-medium ${badge.cls}`}>
                {badge.label}
              </span>
              <span className="text-gray-400 leading-relaxed">{f.text}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function ScheduledTasks() {
  const { data, isLoading, isError, refetch, isFetching } = useScheduledTasks()
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-white">定时任务</h2>
          <p className="mt-0.5 text-xs text-gray-500">
            系统后台运行的全部定时任务 · 倒计时每秒刷新 · 任务元数据每 10 秒同步
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="shrink-0 text-xs text-gray-300 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 rounded px-3 py-1.5 transition-colors"
        >
          {isFetching ? '刷新中…' : '刷新'}
        </button>
      </div>

      {isLoading && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg py-10 text-center text-xs text-gray-600">
          加载中…
        </div>
      )}

      {isError && !isLoading && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg py-10 text-center space-y-2">
          <p className="text-xs text-gray-500">加载失败</p>
          <button
            onClick={() => refetch()}
            className="text-xs text-cyan-400 hover:text-cyan-300"
          >
            重试
          </button>
        </div>
      )}

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {data.map(t => (
            <TaskCard key={t.id} task={t} now={now} />
          ))}
        </div>
      )}
    </div>
  )
}
