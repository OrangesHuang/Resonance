import type { DataFlowItem } from '../../api/types'

const STEP_META: Record<string, { label: string; cls: string }> = {
  fetch: { label: '拉取', cls: 'bg-sky-500/15 text-sky-300 border-sky-500/30' },
  derive: { label: '加工', cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  write: { label: '写入', cls: 'bg-green-500/15 text-green-300 border-green-500/30' },
  offline: { label: '离线', cls: 'bg-gray-500/15 text-gray-300 border-gray-500/30' },
}

export default function FlowSteps({ flow }: { flow: DataFlowItem[] }) {
  if (!flow || flow.length === 0) return null
  return (
    <ol className="space-y-1.5">
      {flow.map((f, i) => {
        const meta = STEP_META[f.step] ?? STEP_META.offline
        return (
          <li key={i} className="flex items-start gap-2 text-xs">
            <span className={`shrink-0 mt-px px-1.5 py-0.5 rounded border text-[10px] leading-4 ${meta.cls}`}>
              {meta.label}
            </span>
            <span className="text-gray-400 leading-5">{f.text}</span>
          </li>
        )
      })}
    </ol>
  )
}
