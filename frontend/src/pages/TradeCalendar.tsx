import { useState } from 'react'
import { useCalendarDays, useRefreshCalendar } from '../hooks/useCalendar'
import MiniMonth from '../components/MiniMonth'
import { buildMonthCells, classifyDay, toKey, pad, WEEK_HEADERS, KIND_LABEL } from '../utils/calendar'

type Mode = 'month' | 'year'

const LEGEND = [
  { label: '交易日', cls: 'bg-gray-900 border-gray-800' },
  { label: '周末', cls: 'bg-gray-900/40 border-gray-800/40' },
  { label: '休市', cls: 'bg-amber-500/10 border-amber-500/30' },
  { label: '今日', cls: 'bg-gray-900 border-gray-800 ring-2 ring-blue-500' },
]

const BIG_KIND: Record<string, string> = {
  trading: 'bg-gray-900 border-gray-800 text-gray-200',
  weekend: 'bg-gray-900/40 border-gray-800/40 text-gray-600',
  holiday: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
  out: 'bg-gray-900/20 border-gray-800/30 text-gray-700',
}

function ym(year: number, month: number): number {
  return year * 12 + month
}

function StatCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-2">{title}</div>
      {children}
    </div>
  )
}

export default function TradeCalendar() {
  const now = new Date()
  const [view, setView] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 })
  const [mode, setMode] = useState<Mode>('month')
  const { data, isLoading, error } = useCalendarDays(view.year)
  const refresh = useRefreshCalendar()

  if (error) {
    return <div className="text-red-400 text-center py-20">连接后端失败，请确认服务已启动</div>
  }
  if (isLoading || !data) {
    return <div className="text-gray-400 text-center py-20">加载中...</div>
  }

  const [lo, hi] = data.range
  const tradingSet = new Set(data.days)
  const todayStr = data.today
  const todayYear = Number(todayStr.slice(0, 4))

  const loYear = lo ? Number(lo.slice(0, 4)) : null
  const hiYear = hi ? Number(hi.slice(0, 4)) : null
  const loYM = lo ? ym(Number(lo.slice(0, 4)), Number(lo.slice(5, 7))) : null
  const hiYM = hi ? ym(Number(hi.slice(0, 4)), Number(hi.slice(5, 7))) : null
  const curYM = ym(view.year, view.month)
  const canPrev = mode === 'year'
    ? loYear == null || view.year > loYear
    : loYM == null || curYM > loYM
  const canNext = mode === 'year'
    ? hiYear == null || view.year < hiYear
    : hiYM == null || curYM < hiYM

  const monthPrefix = `${view.year}-${pad(view.month)}`
  const monthTrading = data.days.filter(d => d.startsWith(monthPrefix)).length
  const before = data.days.filter(d => d < todayStr)
  const after = data.days.filter(d => d > todayStr)
  const prevDay = before.length ? before[before.length - 1] : null
  const nextDay = after.length ? after[0] : null
  const showTodayStats = view.year === todayYear

  const goPrev = () =>
    setView(v =>
      mode === 'year'
        ? { year: v.year - 1, month: v.month }
        : v.month === 1 ? { year: v.year - 1, month: 12 } : { year: v.year, month: v.month - 1 })
  const goNext = () =>
    setView(v =>
      mode === 'year'
        ? { year: v.year + 1, month: v.month }
        : v.month === 12 ? { year: v.year + 1, month: 1 } : { year: v.year, month: v.month + 1 })
  const openMonth = (month: number) => {
    setView(v => ({ year: v.year, month }))
    setMode('month')
  }

  const cells = buildMonthCells(view.year, view.month)

  return (
    <div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <h2 className="text-xl font-bold text-white">交易日历</h2>
        {hi && <span className="text-xs text-gray-500">数据覆盖至 {hi}</span>}
        {data.updated_at && <span className="text-xs text-gray-600">最后更新 {data.updated_at}</span>}
        <div className="ml-auto flex items-center gap-2">
          {refresh.isSuccess && refresh.data && (
            <span className="text-xs text-gray-500">已同步 {refresh.data.count} 个交易日</span>
          )}
          <button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            className="px-3 py-1.5 rounded text-sm bg-gray-800 text-gray-200 border border-gray-700 hover:border-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {refresh.isPending ? '同步中…' : '手动同步'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title={`本月交易日（${view.month}月）`}>
          <span className="text-2xl font-mono text-white">{monthTrading}</span>
          <span className="text-xs text-gray-500 ml-1">天</span>
        </StatCard>
        <StatCard title={`全年交易日（${view.year}）`}>
          <span className="text-2xl font-mono text-white">{data.total}</span>
          <span className="text-xs text-gray-500 ml-1">天</span>
        </StatCard>
        <StatCard title="上一交易日">
          <span className="text-lg font-mono text-gray-200">{showTodayStats && prevDay ? prevDay : '-'}</span>
        </StatCard>
        <StatCard title="下一交易日">
          <span className="text-lg font-mono text-gray-200">{showTodayStats && nextDay ? nextDay : '-'}</span>
        </StatCard>
      </div>

      <div className="flex items-center justify-between mb-4">
        <div className="inline-flex rounded-lg border border-gray-800 overflow-hidden">
          {(['month', 'year'] as Mode[]).map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-3 py-1.5 text-sm transition-colors ${
                mode === m ? 'bg-gray-800 text-white' : 'bg-gray-900 text-gray-500 hover:text-gray-300'
              }`}
            >
              {m === 'month' ? '月视图' : '年视图'}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={goPrev}
            disabled={!canPrev}
            className="px-3 py-1 rounded text-sm bg-gray-800 text-gray-300 border border-gray-700 hover:border-gray-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ‹ {mode === 'year' ? '上年' : '上月'}
          </button>
          <span className="text-base font-medium text-white min-w-[7rem] text-center">
            {mode === 'year' ? `${view.year} 年` : `${view.year} 年 ${view.month} 月`}
          </span>
          <button
            onClick={goNext}
            disabled={!canNext}
            className="px-3 py-1 rounded text-sm bg-gray-800 text-gray-300 border border-gray-700 hover:border-gray-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {mode === 'year' ? '下年' : '下月'} ›
          </button>
        </div>
      </div>

      {mode === 'year' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {Array.from({ length: 12 }, (_, i) => i + 1).map(month => (
            <MiniMonth
              key={month}
              year={view.year}
              month={month}
              tradingSet={tradingSet}
              todayStr={todayStr}
              lo={lo}
              hi={hi}
              onSelect={openMonth}
            />
          ))}
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="grid grid-cols-7 gap-1.5 mb-1.5">
            {WEEK_HEADERS.map(w => (
              <div key={w} className="text-center text-xs text-gray-500 py-1">{w}</div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-1.5">
            {cells.map((day, i) => {
              if (day == null) return <div key={`blank-${i}`} />
              const dateStr = toKey(view.year, view.month, day)
              const dow = new Date(view.year, view.month - 1, day).getDay()
              const kind = classifyDay(dateStr, dow, tradingSet, lo, hi)
              const isToday = dateStr === todayStr
              const label = KIND_LABEL[kind]
              return (
                <div
                  key={dateStr}
                  title={label ? `${dateStr} · ${label}` : dateStr}
                  className={`aspect-square flex flex-col items-center justify-center rounded-md border font-mono text-sm ${BIG_KIND[kind]} ${isToday ? 'ring-2 ring-blue-500' : ''}`}
                >
                  <span>{day}</span>
                  {kind === 'holiday' && <span className="text-[10px] leading-none mt-0.5">休</span>}
                </div>
              )
            })}
          </div>

          <div className="flex items-center gap-4 mt-4 flex-wrap">
            {LEGEND.map(item => (
              <div key={item.label} className="flex items-center gap-1.5">
                <span className={`inline-block w-3 h-3 rounded border ${item.cls}`} />
                <span className="text-xs text-gray-500">{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
