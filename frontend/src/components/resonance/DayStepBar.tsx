interface Props {
  displayDate: string
  canPrev: boolean
  canNext: boolean
  onStep: (dir: number) => void
}

const BTN = 'px-3 py-1.5 rounded text-sm bg-gray-800 text-gray-200 border border-gray-700 hover:border-gray-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors'

export default function DayStepBar({ displayDate, canPrev, canNext, onStep }: Props) {
  return (
    <div className="bg-gray-950/95 backdrop-blur border border-gray-800 rounded-lg px-3 py-2 flex items-center gap-2 flex-wrap">
      <button onClick={() => onStep(-1)} disabled={!canPrev} className={BTN}>← 上一日</button>
      <span className="text-sm font-mono text-sky-400 min-w-[92px] text-center">{displayDate || '-'}</span>
      <button onClick={() => onStep(1)} disabled={!canNext} className={BTN}>下一日 →</button>
      <span className="ml-auto text-[11px] text-gray-600 hidden md:inline">逐日回放练盘感（键盘 ← → 亦可）· 点选/缩放任意图表，全部联动</span>
    </div>
  )
}
