import type { SchedulerJobInfo } from '../../api/types'

const JOB_LABELS: Record<string, string> = {
  realtime_poll: '盘中实时轮询',
  preload_kline: '预加载K线',
  daily_analysis: '日度分析',
  fetch_shares: '份额抓取',
  fetch_sentiment: '情绪抓取',
  sync_calendar: '日历同步',
  cleanup: '实时数据清理',
}

function fmtNext(t: string | null): string {
  if (!t) return '—'
  return t.replace('T', ' ').split('+')[0].slice(0, 19)
}

export default function SchedulerPanel({ jobs }: { jobs: SchedulerJobInfo[] }) {
  if (jobs.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg py-6 text-center text-xs text-gray-600">
        无定时任务
      </div>
    )
  }
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-500 border-b border-gray-800">
            <th className="text-left px-3 py-2 font-normal">任务</th>
            <th className="text-left px-3 py-2 font-normal">下次运行</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map(j => (
            <tr key={j.id} className="border-b border-gray-800/60 last:border-0">
              <td className="px-3 py-2 text-gray-300">{JOB_LABELS[j.id] ?? j.id}</td>
              <td className="px-3 py-2 text-gray-500 font-mono">{fmtNext(j.next_run)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
