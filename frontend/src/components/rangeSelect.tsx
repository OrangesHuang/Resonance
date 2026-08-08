import { useMemo, useRef, useState } from 'react'

export interface RangeSelection {
  start: string | null
  end: string | null
}

export function useRangeSelect() {
  const [mode, setMode] = useState(false)
  const [sel, setSel] = useState<RangeSelection>({ start: null, end: null })
  const ref = useRef({ mode, sel })
  ref.current = { mode, sel }

  /** 由 ECharts brushEnd 设置区间(自动归一为 start <= end) */
  const setRange = (start: string, end: string) => {
    setSel(start <= end ? { start, end } : { start: end, end: start })
  }

  const toggle = () => {
    setMode(m => !m)
    setSel({ start: null, end: null })
  }
  const clear = () => setSel({ start: null, end: null })

  const band = useMemo(() =>
    (sel.start && sel.end)
      ? [{
          xAxis: sel.start,
          itemStyle: {
            color: 'rgba(56, 189, 248, 0.18)',
            borderColor: '#0ea5e9',
            borderWidth: 1,
          },
        }, { xAxis: sel.end }]
      : [],
  [sel])

  return { mode, sel, setRange, toggle, clear, band }
}

export function RangeToolbar({ hook, isMobile }: { hook: ReturnType<typeof useRangeSelect>; isMobile?: boolean }) {
  return (
    <div className="flex items-center gap-2 mb-1 text-xs">
      <button
        onClick={hook.toggle}
        className={`px-2 py-1 rounded border transition-colors ${
          hook.mode
            ? 'bg-sky-600/20 text-sky-300 border-sky-600/40'
            : 'bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-500'
        }`}
      >
        区间统计
      </button>
      {hook.mode && (
        <span className="text-gray-500">
          {hook.sel.start != null && hook.sel.end != null
            ? `已选 ${hook.sel.start} ~ ${hook.sel.end}`
            : isMobile ? '依次点击K线选择起止日期' : '拖拽框选区间起止日期'}
        </span>
      )}
    </div>
  )
}
