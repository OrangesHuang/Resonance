import { useState, useRef, useEffect } from "react"
import type { EtfInfo } from "../../api/types"
import { usePinnedEtfs } from "../../hooks/usePinnedEtfs"
import useIsMobile from "../../hooks/useIsMobile"

interface Props {
  value: string
  onChange: (code: string) => void
  etfList: EtfInfo[]
}

export default function EtfSelector({ value, onChange, etfList }: Props) {
  const { pinned: pinnedCodes, togglePin } = usePinnedEtfs()
  const [expanded, setExpanded] = useState(false)
  const [query, setQuery] = useState("")
  const isMobile = useIsMobile()
  const panelRef = useRef<HTMLDivElement>(null)

  const validPinned = pinnedCodes.filter(c => etfList.some(e => e.code === c))
  const pinnedEtfs = validPinned
    .map(c => etfList.find(e => e.code === c))
    .filter((e): e is EtfInfo => !!e)

  useEffect(() => {
    if (!expanded) return
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setExpanded(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [expanded])

  useEffect(() => {
    if (!expanded) setQuery("")
  }, [expanded])

  const currentEtf = etfList.find(e => e.code === value)

  const q = query.trim().toLowerCase()
  const filtered = q
    ? etfList.filter(
        e => e.code.includes(q) || e.name.toLowerCase().includes(q) || e.idx.toLowerCase().includes(q)
      )
    : etfList

  const groups: { idx: string; items: EtfInfo[] }[] = []
  for (const etf of filtered) {
    let g = groups.find(g => g.idx === etf.idx)
    if (!g) {
      g = { idx: etf.idx, items: [] }
      groups.push(g)
    }
    g.items.push(etf)
  }

  return (
    <div ref={panelRef} className="relative">
      {/* Pinned chips bar */}
      <div className="flex flex-wrap items-center gap-1.5">
        {currentEtf && (
          <span className="text-xs text-gray-500 mr-1 hidden sm:inline">
            {currentEtf.code} {currentEtf.name}
          </span>
        )}
        {pinnedEtfs.map(etf => {
          const active = etf.code === value
          return (
            <button
              key={etf.code}
              onClick={() => onChange(etf.code)}
              className={`
                inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium
                border transition-colors
                ${active
                  ? "bg-sky-600/80 text-white border-sky-500"
                  : "bg-gray-800 text-gray-300 border-gray-700 hover:border-gray-500"}
              `}
            >
              {etf.idx}
              <span
                role="button"
                onClick={e => { e.stopPropagation(); togglePin(etf.code) }}
                className="ml-0.5 text-gray-500 hover:text-red-400 cursor-pointer"
                title="取消置顶"
              >
                ×
              </span>
            </button>
          )
        })}
        <button
          onClick={() => setExpanded(v => !v)}
          className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs
                     text-gray-400 border border-dashed border-gray-700
                     hover:border-gray-500 hover:text-gray-200 transition-colors"
        >
          {expanded ? "收起" : "全部ETF"} {expanded ? "▴" : "▾"}
        </button>
      </div>

      {/* Expanded panel */}
      {expanded && (
        <div className={`
          ${isMobile ? "relative" : "absolute left-0 right-0 mt-1"}
          z-30 bg-gray-900 border border-gray-700 rounded-lg shadow-xl
        `}>
          <div className="p-2 border-b border-gray-800">
            <input
              autoFocus={!isMobile}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="搜索代码/名称/板块…"
              className="w-full px-2.5 py-1.5 rounded text-xs bg-gray-800 text-gray-200
                         border border-gray-700 focus:outline-none focus:border-sky-500 placeholder:text-gray-600"
            />
          </div>
          <div className="max-h-72 overflow-y-auto">
            {groups.length === 0 && (
              <div className="px-3 py-4 text-xs text-gray-500 text-center">无匹配结果</div>
            )}
            {groups.map(g => (
              <div key={g.idx}>
                <div className="px-3 pt-2 pb-1 text-[11px] text-gray-500 sticky top-0 bg-gray-900">{g.idx}</div>
                {g.items.map(etf => {
                  const isPinned = validPinned.includes(etf.code)
                  const active = etf.code === value
                  return (
                    <div
                      key={etf.code}
                      className={`
                        flex items-center justify-between px-3 py-2 cursor-pointer
                        hover:bg-gray-800/60 transition-colors
                        ${active ? "border-l-2 border-sky-500 bg-gray-800/30" : "border-l-2 border-transparent"}
                      `}
                      onClick={() => { onChange(etf.code); if (!isMobile) setExpanded(false) }}
                    >
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-mono ${active ? "text-sky-400" : "text-gray-500"}`}>
                          {etf.code}
                        </span>
                        <span className={`text-sm ${active ? "text-white" : "text-gray-300"}`}>
                          {etf.name}
                        </span>
                      </div>
                      <button
                        onClick={e => { e.stopPropagation(); togglePin(etf.code) }}
                        className={`
                          px-1.5 py-0.5 rounded text-xs transition-colors
                          ${isPinned
                            ? "text-sky-400 bg-sky-900/30 hover:text-red-400"
                            : "text-gray-600 hover:text-sky-400"}
                        `}
                        title={isPinned ? "取消置顶" : "置顶"}
                      >
                        {isPinned ? "★" : "☆"}
                      </button>
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
