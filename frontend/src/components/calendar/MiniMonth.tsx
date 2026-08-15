import { buildMonthCells, classifyDay, toKey, WEEK_HEADERS, KIND_LABEL } from '../../utils/calendar'
import type { DayKind } from '../../utils/calendar'

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
  coverage?: Record<string, number>
  slotStart?: string | null
  onSelect: (month: number) => void
}

export default function MiniMonth({ year, month, tradingSet, todayStr, lo, hi, coverage, slotStart, onSelect }: Props) {
  const cells = buildMonthCells(year, month)
  const tradingCount = cells.filter(d => d != null && tradingSet.has(toKey(year, month, d))).length
  // 本月槽位(起始日~今天)与已覆盖数
  const slotDays = cells.filter((d): d is number => {
    if (d == null || !tradingSet.has(toKey(year, month, d))) return false
    const ds = toKey(year, month, d)
    if (ds > todayStr) return false
    return !slotStart || ds >= slotStart
  })
  const covered = slotDays.filter(d => (coverage?.[toKey(year, month, d)] ?? 0) > 0).length
  const ratio = slotDays.length > 0 ? covered / slotDays.length : null

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
      <div className="flex items-baseline justify-between mb-1.5">
        <button
          onClick={() => onSelect(month)}
          className="text-sm font-medium text-gray-200 hover:text-white transition-colors"
          title={`查看 ${year} 年 ${month} 月`}
        >
          {month}月
        </button>
        <span className="text-[10px] text-gray-500 font-mono">
          {tradingCount} 天 · 槽位 {slotDays.length > 0 ? `${covered}/${slotDays.length}` : '-'}
        </span>
      </div>
      {ratio != null && slotDays.length > 0 && (
        <div className="mb-1.5 h-1 bg-gray-800 rounded overflow-hidden">
          <div
            className={`h-full ${ratio >= 1 ? 'bg-green-400' : ratio > 0 ? 'bg-amber-400' : 'bg-red-400'}`}
            style={{ width: `${Math.round(ratio * 100)}%` }}
          />
        </div>
      )}

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
          // 数据槽位覆盖点: 绿=四源全, 黄=部分, 红=槽位日无数据(仅槽位区间内展示)
          const c = coverage?.[dateStr]
          const showDot = kind === 'trading' && dateStr <= todayStr
            && (!slotStart || dateStr >= slotStart) && c != null
          const dotCls = showDot ? (c >= 4 ? 'bg-green-400' : c >= 1 ? 'bg-amber-400' : 'bg-red-400') : ''
          return (
            <div
              key={dateStr}
              title={`${dateStr}${showDot ? ` · 数据覆盖 ${c}/4` : ''}${label ? ` · ${label}` : ''}`}
              className={`relative flex h-5 items-center justify-center rounded font-mono text-[11px] ${MINI_KIND[kind]} ${isToday ? 'ring-1 ring-blue-500' : ''}`}
            >
              {day}
              {dotCls && <span className={`absolute bottom-0.5 w-1 h-1 rounded-full ${dotCls}`} />}
            </div>
          )
        })}
      </div>
    </div>
  )
}
