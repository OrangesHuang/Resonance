import { buildMonthCells, classifyDay, toKey, WEEK_HEADERS, KIND_LABEL } from '../utils/calendar'
import type { DayKind } from '../utils/calendar'

const MINI_KIND: Record<DayKind, string> = {
  trading: 'bg-gray-700/60 text-gray-100',
  weekend: 'text-gray-600',
  holiday: 'bg-amber-500/15 text-amber-400',
  out: 'text-gray-700',
}

interface Props {
  year: number
  month: number
  tradingSet: Set<string>
  todayStr: string
  lo: string | null
  hi: string | null
  onSelect: (month: number) => void
}

export default function MiniMonth({ year, month, tradingSet, todayStr, lo, hi, onSelect }: Props) {
  const cells = buildMonthCells(year, month)
  const tradingCount = cells.filter(d => d != null && tradingSet.has(toKey(year, month, d))).length

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
      <div className="flex items-baseline justify-between mb-2">
        <button
          onClick={() => onSelect(month)}
          className="text-sm font-medium text-gray-200 hover:text-white transition-colors"
          title={`查看 ${year} 年 ${month} 月`}
        >
          {month}月
        </button>
        <span className="text-xs text-gray-500 font-mono">{tradingCount} 天</span>
      </div>

      <div className="grid grid-cols-7 gap-0.5 text-center text-[10px] mb-0.5">
        {WEEK_HEADERS.map((w, i) => (
          <div key={w} className={i === 0 || i === 6 ? 'text-gray-700' : 'text-gray-600'}>{w}</div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-0.5">
        {cells.map((day, i) => {
          if (day == null) return <div key={`e-${i}`} />
          const dateStr = toKey(year, month, day)
          const dow = new Date(year, month - 1, day).getDay()
          const kind = classifyDay(dateStr, dow, tradingSet, lo, hi)
          const isToday = dateStr === todayStr
          const label = KIND_LABEL[kind]
          return (
            <div
              key={dateStr}
              title={label ? `${dateStr} · ${label}` : dateStr}
              className={`flex h-5 items-center justify-center rounded font-mono text-[11px] ${MINI_KIND[kind]} ${isToday ? 'ring-1 ring-blue-500' : ''}`}
            >
              {day}
            </div>
          )
        })}
      </div>
    </div>
  )
}
