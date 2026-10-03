import { Fragment, useState } from 'react'
import { Link } from 'react-router-dom'
import { useDeleteEtf } from '../../hooks/useEtfManage'
import type { EtfManageRow, JobState } from '../../api/types'

const DEPTH_OPTIONS = [60, 120, 160, 250, 500]
const DEFAULT_DEPTH = 160
const TH = 'text-left py-2 pr-3 font-medium whitespace-nowrap text-gray-500'
const TD = 'py-2 pr-3 align-top whitespace-nowrap'
const VERSION_LABEL: Record<string, string> = { stable: '正式', beta: 'Beta', band: '波段' }

interface Props {
  rows: EtfManageRow[]
  jobs: JobState[]
  backfillBusy: boolean
  onBackfill: (code: string, days: number) => void
}

function ProgressBar({ job }: { job: JobState }) {
  const pct = job.total > 0 ? Math.min(100, Math.round((job.current / job.total) * 100)) : 0
  return (
    <div className="py-1.5">
      <div className="flex items-center gap-2 text-[11px] text-gray-400">
        <span className="text-blue-400">回填中</span>
        <span className="truncate max-w-[70ch]">{job.message}</span>
        <span className="text-gray-600">{pct}%</span>
      </div>
      <div className="mt-1 h-1.5 rounded bg-gray-800 overflow-hidden">
        <div className="h-full bg-blue-500 transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function EtfTable({ rows, jobs, backfillBusy, onBackfill }: Props) {
  const [depths, setDepths] = useState<Record<string, number>>({})
  const [confirmCode, setConfirmCode] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const del = useDeleteEtf()

  const jobFor = (code: string) =>
    jobs.find((j) => j.params.code === code && (j.status === 'running' || j.status === 'pending'))

  const handleDelete = (code: string) => {
    setError(null)
    del.mutate(code, {
      onSuccess: () => setConfirmCode(null),
      onError: (e: Error) => setError(e.message),
    })
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 overflow-x-auto">
      {error && (
        <div className="mb-3 flex items-start justify-between gap-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-300 hover:text-white">
            ×
          </button>
        </div>
      )}

      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-800">
            <th className={TH}>标的</th>
            <th className={TH}>指数 / 市场</th>
            <th className={TH}>数据覆盖</th>
            <th className={TH}>策略</th>
            <th className={TH}>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const job = jobFor(row.code)
            const confirming = confirmCode === row.code
            const cov = row.coverage
            return (
              <Fragment key={row.code}>
                <tr className="border-b border-gray-800/50 last:border-0">
                  <td className={TD}>
                    <div className="font-mono text-gray-200">{row.code}</div>
                    <div className="text-gray-500">{row.name}</div>
                  </td>
                  <td className={TD}>
                    <div className="text-gray-300">{row.idx || '—'}</div>
                    <div className="text-gray-600">{row.market === 'sh' ? '上交所' : '深交所'}</div>
                  </td>
                  <td className={TD}>
                    {cov.first_date ? (
                      <>
                        <div className="text-gray-300">
                          {cov.first_date} ~ {cov.last_date}
                        </div>
                        <div className="text-gray-600">
                          {cov.daily_rows} 日度 · 份额至 {cov.shares_last_date ?? '—'} · 快照 {cov.realtime_rows}
                        </div>
                      </>
                    ) : (
                      <span className="text-amber-400">未拉取（点「回填」初始化）</span>
                    )}
                  </td>
                  <td className={TD}>
                    {row.strategy_versions.map((v) => (
                      <span
                        key={v}
                        className="mr-1 rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-400"
                      >
                        {VERSION_LABEL[v] ?? v}
                      </span>
                    ))}
                  </td>
                  <td className={TD}>
                    <div className="flex items-center gap-2">
                      <select
                        className="bg-gray-950 border border-gray-700 rounded px-1.5 py-1 text-xs text-gray-300"
                        value={depths[row.code] ?? DEFAULT_DEPTH}
                        onChange={(e) => setDepths((d) => ({ ...d, [row.code]: Number(e.target.value) }))}
                        disabled={!!job}
                      >
                        {DEPTH_OPTIONS.map((d) => (
                          <option key={d} value={d}>
                            {d} 交易日
                          </option>
                        ))}
                      </select>
                      <button
                        className="rounded bg-gray-800 px-2 py-1 text-gray-200 hover:bg-gray-700 disabled:opacity-50"
                        disabled={!!job || row.active_job || backfillBusy}
                        onClick={() => onBackfill(row.code, depths[row.code] ?? DEFAULT_DEPTH)}
                      >
                        回填
                      </button>
                      <Link className="text-blue-400 hover:text-blue-300" to={`/etf/${row.code}`}>
                        详情
                      </Link>
                      <Link className="text-blue-400 hover:text-blue-300" to={`/resonance?code=${row.code}`}>
                        共振
                      </Link>
                      {row.protected ? (
                        <span className="text-gray-600" title="策略基准标的, 不可删除">
                          基准
                        </span>
                      ) : (
                        <button
                          className="text-red-400 hover:text-red-300 disabled:opacity-50"
                          disabled={!!job || row.active_job || del.isPending}
                          onClick={() => setConfirmCode(confirming ? null : row.code)}
                        >
                          删除
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {job && (
                  <tr className="border-b border-gray-800/50">
                    <td colSpan={5} className="px-0">
                      <ProgressBar job={job} />
                    </td>
                  </tr>
                )}
                {confirming && (
                  <tr className="border-b border-gray-800/50 bg-red-500/5">
                    <td colSpan={5} className="py-2">
                      <div className="flex items-center gap-3 flex-wrap text-xs">
                        <span className="text-red-400">
                          将永久删除 {row.code} {row.name}:{' '}
                          <b>{cov.daily_rows}</b> 行日度数据 + <b>{cov.realtime_rows}</b> 行实时快照，不可恢复
                        </span>
                        <button
                          className="rounded bg-red-600 px-2 py-1 font-medium text-white hover:bg-red-500 disabled:opacity-50"
                          disabled={del.isPending}
                          onClick={() => handleDelete(row.code)}
                        >
                          {del.isPending ? '删除中…' : '确认删除'}
                        </button>
                        <button
                          className="rounded bg-gray-800 px-2 py-1 text-gray-300 hover:bg-gray-700"
                          onClick={() => setConfirmCode(null)}
                        >
                          取消
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
          {rows.length === 0 && (
            <tr>
              <td className={TD} colSpan={5}>
                加载中…
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
