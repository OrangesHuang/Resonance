import { useEffect, useState } from 'react'
import { useDataJobs, useStartJob } from '../hooks/useData'
import { useEtfManageList } from '../hooks/useEtfManage'
import AddEtfForm from '../components/etfmanage/AddEtfForm'
import EtfTable from '../components/etfmanage/EtfTable'

export default function EtfManage() {
  const [poll, setPoll] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { data: rows } = useEtfManageList()
  const jobsQuery = useDataJobs(poll)
  const startJob = useStartJob()

  const jobs = jobsQuery.data ?? []
  const activeJobs = jobs.filter((j) => j.status === 'running' || j.status === 'pending')

  useEffect(() => {
    if (activeJobs.length > 0) {
      setPoll(true)
    } else if (poll) {
      const timer = setTimeout(() => setPoll(false), 2000)
      return () => clearTimeout(timer)
    }
  }, [activeJobs.length, poll])

  const handleBackfill = (code: string, days: number) => {
    setError(null)
    setNotice(null)
    setPoll(true)
    startJob.mutate(
      { task: 'backfill_etf', params: { code, days } },
      { onError: (e: Error) => setError(e.message) },
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex items-baseline gap-3 flex-wrap">
        <h2 className="text-xl font-bold">ETF 管理</h2>
        <span className="text-xs text-gray-500">
          动态添加/删除监控标的 · 添加后按标的初始化拉取 · 删除将清除该标的全部历史数据
        </span>
      </div>

      <AddEtfForm
        onAdded={(code, name) => {
          setError(null)
          setNotice(`${code} ${name} 已加入监控列表，请在下方点「回填」初始化数据`)
        }}
      />

      {notice && (
        <div className="flex items-start justify-between gap-3 rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-400">
          <span>{notice}</span>
          <button onClick={() => setNotice(null)} className="text-emerald-300 hover:text-white">
            ×
          </button>
        </div>
      )}
      {error && (
        <div className="flex items-start justify-between gap-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-300 hover:text-white">
            ×
          </button>
        </div>
      )}

      <EtfTable
        rows={rows ?? []}
        jobs={jobs}
        backfillBusy={activeJobs.some((j) => j.task === 'backfill_etf')}
        onBackfill={handleBackfill}
      />

      <p className="text-[11px] text-gray-600 leading-relaxed">
        说明：回填复用「ETF 日度 → 份额 → 折算修正 → 综合概率重算」完整链路，进度可在本页与「数据管理」页查看。
        删除为硬删除（清单 + 日度数据 + 实时快照），不可恢复——操作前可备份
        <span className="font-mono"> ~/.etf-monitor/etf_monitor.db</span>。510300 / 589680 为策略基准标的，不可删除。
      </p>
    </div>
  )
}
