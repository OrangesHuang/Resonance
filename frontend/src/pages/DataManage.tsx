import { useEffect, useState } from 'react'
import { useDataStatus, useDataJobs, useStartJob } from '../hooks/useData'
import SourceCard from '../components/data/SourceCard'
import JobsPanel from '../components/data/JobsPanel'
import SchedulerPanel from '../components/data/SchedulerPanel'
import type { JobState } from '../api/types'

function fmtRange(r: [string | null, string | null] | undefined): string {
  if (!r || !r[0] || !r[1]) return '—'
  return `${r[0]} ~ ${r[1]}`
}

const toISO = (d: Date) => d.toISOString().slice(0, 10)

function defaultRange(): { start: string; end: string } {
  const today = new Date()
  const start = new Date(today)
  start.setFullYear(today.getFullYear() - 1)
  return { start: toISO(start), end: toISO(today) }
}

const DATE_CLS = 'bg-gray-950 border border-gray-800 rounded px-2 py-1 text-gray-200 [color-scheme:dark]'

export default function DataManage() {
  const [polling, setPolling] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [range, setRange] = useState(defaultRange)
  const [force, setForce] = useState(false)

  const status = useDataStatus(polling)
  const jobs = useDataJobs(polling)
  const startJob = useStartJob()

  const allJobs: JobState[] = jobs.data ?? status.data?.running ?? []
  const active = allJobs.filter(j => j.status === 'running' || j.status === 'pending')
  const runningTasks = new Set(active.map(j => j.task))
  const anyRunning = active.length > 0
  const rebuildRunning = runningTasks.has('rebuild_all')

  useEffect(() => {
    if (anyRunning) {
      setPolling(true)
    } else if (polling) {
      const t = setTimeout(() => setPolling(false), 2000)
      return () => clearTimeout(t)
    }
  }, [anyRunning, polling])

  const run = (task: string, params?: Record<string, string | number | boolean>) => {
    setPolling(true)
    setConfirming(false)
    setError(null)
    startJob.mutate(
      { task, params },
      { onError: (e: Error) => setError(e.message) },
    )
  }

  const rangeParams = { start_date: range.start, end_date: range.end, force }
  const progressFor = (task: string) => {
    const j = active.find(x => x.task === task)
    return j ? { current: j.current, total: j.total, message: j.message } : null
  }

  const labelOf = (task: string) => status.data?.jobs.find(j => j.task === task)?.label ?? task

  if (status.isLoading) return <div className="text-gray-500 text-center py-10">加载中…</div>
  if (status.isError || !status.data) return <div className="text-red-400 text-center py-10">数据状态加载失败</div>

  const s = status.data.sources

  const etfLevel = s.etf_daily.total_records === 0 ? 'empty' : s.etf_daily.records_with_shares === 0 ? 'warn' : 'ok'
  const shareLevel = s.etf_daily.records_with_shares === 0 ? 'empty' : s.etf_daily.records_with_shares < s.etf_daily.total_records ? 'warn' : 'ok'
  const sentCount = Math.min(s.turnover.count, s.margin.count)
  const sentLevel = sentCount === 0 ? 'empty' : sentCount < 20 ? 'warn' : 'ok'
  const calLevel = s.calendar.count === 0 ? 'empty' : 'ok'
  const LEVEL_TEXT = { ok: '充足', warn: '部分缺失', empty: '空' }

  const startRebuild = () => run('rebuild_all', rangeParams)

  return (
    <div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <h2 className="text-xl font-bold text-white">数据管理</h2>
        <span className="text-xs text-gray-500">统一拉取与生成 · 内置定时任务自动增量</span>
        <div className="ml-auto">
          {confirming ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-amber-400">确认重建全部数据？</span>
              <button onClick={startRebuild} disabled={anyRunning}
                className="px-3 py-1.5 rounded text-sm bg-red-600 text-white hover:bg-red-500 disabled:opacity-50 transition-colors">
                确认重建
              </button>
              <button onClick={() => setConfirming(false)}
                className="px-3 py-1.5 rounded text-sm bg-gray-800 text-gray-300 border border-gray-700 hover:border-gray-500 transition-colors">
                取消
              </button>
            </div>
          ) : (
            <button onClick={() => setConfirming(true)} disabled={anyRunning}
              className="px-3 py-1.5 rounded text-sm bg-red-600/90 text-white hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
              {rebuildRunning ? '重建中…' : '一键重建全部数据'}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-3 text-gray-500 hover:text-gray-300">×</button>
        </div>
      )}

      <div className="bg-gray-900/40 border border-dashed border-gray-800 rounded-lg p-3 mb-4 text-xs text-gray-500 leading-relaxed">
        首次使用（空数据库）请点击「一键重建全部数据」，系统按 交易日历 → ETF日度 → 份额 → 市场情绪 顺序自动拉取全量数据；日常增量由内置定时任务在收盘后自动完成。
      </div>

      <div className="flex items-center gap-4 mb-4 flex-wrap text-xs text-gray-500">
        <span>拉取时间范围：</span>
        <label className="flex items-center gap-1">开始
          <input type="date" value={range.start} max={range.end}
            onChange={e => setRange(r => ({ ...r, start: e.target.value }))} className={DATE_CLS} />
        </label>
        <label className="flex items-center gap-1">结束
          <input type="date" value={range.end} min={range.start} max={toISO(new Date())}
            onChange={e => setRange(r => ({ ...r, end: e.target.value }))} className={DATE_CLS} />
        </label>
        <label className="flex items-center gap-1.5 text-gray-400 cursor-pointer" title="勾选后忽略已有数据，强制重新拉取并覆盖">
          <input type="checkbox" checked={force} onChange={e => setForce(e.target.checked)}
            className="accent-sky-500 w-3.5 h-3.5" />
          强制重拉（覆盖已有数据）
        </label>
        <span className="text-gray-600">以下各数据源的拉取均使用此时间范围；不勾选时已存在的日期自动跳过</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <SourceCard title="ETF 日度数据" description="K线三因子分析：价格位置、交易方向、综合概率"
          level={etfLevel} levelText={etfLevel === 'warn' ? '缺份额' : LEVEL_TEXT[etfLevel]}
          stats={[
            { label: '记录数', value: String(s.etf_daily.total_records) },
            { label: '交易日', value: String(s.etf_daily.trading_days) },
            { label: '区间', value: fmtRange(s.etf_daily.date_range) },
          ]}
          actionLabel="回填日度" onAction={() => run('backfill_etf_daily', rangeParams)}
          disabled={runningTasks.has('backfill_etf_daily') || rebuildRunning}
          running={runningTasks.has('backfill_etf_daily')} progress={progressFor('backfill_etf_daily')} />

        <SourceCard title="份额数据" description="ETF 份额净申赎，重算 share_prob（影响份额流向灯）"
          level={shareLevel} levelText={LEVEL_TEXT[shareLevel]}
          stats={[{ label: '含份额记录', value: `${s.etf_daily.records_with_shares} / ${s.etf_daily.total_records}` }]}
          actionLabel="回填份额" onAction={() => run('backfill_shares', rangeParams)}
          disabled={runningTasks.has('backfill_shares') || rebuildRunning}
          running={runningTasks.has('backfill_shares')} progress={progressFor('backfill_shares')} />

        <SourceCard title="市场情绪" description="两市成交额 + 融资余额（全市场指标，需≥20点暖机）"
          level={sentLevel} levelText={sentLevel === 'warn' ? '不足20点' : LEVEL_TEXT[sentLevel]}
          stats={[
            { label: '成交额', value: `${s.turnover.count} 天` },
            { label: '融资余额', value: `${s.margin.count} 天` },
            { label: '区间', value: fmtRange(s.turnover.range) },
          ]}
          actionLabel="拉取情绪" onAction={() => run('fetch_sentiment', rangeParams)}
          disabled={runningTasks.has('fetch_sentiment') || rebuildRunning}
          running={runningTasks.has('fetch_sentiment')} progress={progressFor('fetch_sentiment')} />

        <SourceCard title="交易日历" description="A股交易日历，供回填与定时任务判定"
          level={calLevel} levelText={calLevel === 'ok' ? '正常' : '空'}
          stats={[
            { label: '交易日数', value: String(s.calendar.count) },
            { label: '区间', value: fmtRange(s.calendar.range) },
            { label: '上次同步', value: s.calendar.last_sync ?? '—' },
          ]}
          actionLabel="同步日历" onAction={() => run('sync_calendar')}
          disabled={runningTasks.has('sync_calendar') || rebuildRunning}
          running={runningTasks.has('sync_calendar')} progress={progressFor('sync_calendar')} />
      </div>

      <h3 className="text-sm font-semibold text-white mb-2">任务记录</h3>
      <div className="mb-6">
        <JobsPanel jobs={allJobs} labelOf={labelOf} />
      </div>

      <h3 className="text-sm font-semibold text-white mb-2">定时任务</h3>
      <SchedulerPanel jobs={status.data.scheduler} />
    </div>
  )
}
