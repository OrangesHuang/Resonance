import ReactECharts from 'echarts-for-react'
import type { ResonanceDayIndicator, LightState } from '../api/types'

const STATE_BADGE: Record<LightState, { label: string; cls: string; text: string }> = {
  red: { label: '红灯', cls: 'bg-red-500/20 text-red-400 border-red-500/40', text: 'text-red-400' },
  green: { label: '绿灯', cls: 'bg-green-500/20 text-green-400 border-green-500/40', text: 'text-green-400' },
  gray: { label: '灰灯', cls: 'bg-gray-700/40 text-gray-400 border-gray-700', text: 'text-gray-400' },
}

function fmtVal(v: number | string | null): string {
  if (v === null || v === undefined) return '-'
  return String(v)
}

function WindowSparkline({ window: w }: { window: number[] }) {
  const option = {
    backgroundColor: 'transparent',
    animation: false,
    grid: { left: 46, right: 12, top: 8, bottom: 16 },
    xAxis: { type: 'category', show: false, data: w.map((_, i) => String(i + 1)) },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: '#6b7280', fontSize: 9 },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 10 },
      formatter: (p: Array<{ dataIndex: number; value: number }>) =>
        `窗口第 ${p[0].dataIndex + 1} 天<br/>${p[0].value} 亿元`,
    },
    series: [
      {
        type: 'line',
        data: w,
        symbol: 'none',
        lineStyle: { color: '#60a5fa', width: 1.5 },
        areaStyle: { color: 'rgba(96,165,250,0.08)' },
      },
    ],
  }
  return <ReactECharts option={option} style={{ height: 90 }} notMerge lazyUpdate />
}

export default function EvidenceCard({ ind, highlight }: {
  ind: ResonanceDayIndicator
  highlight: boolean
}) {
  const badge = STATE_BADGE[ind.state]
  const ev = ind.evidence
  const inputEntries = Object.entries(ev.inputs)

  return (
    <div className={`bg-gray-900 border rounded-lg p-4 ${highlight ? 'border-blue-500/60 ring-1 ring-blue-500/40' : 'border-gray-800'}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm font-medium text-gray-200">{ind.name}</span>
        <span className={`px-2 py-0.5 rounded text-xs border ${badge.cls}`}>{badge.label}</span>
        <span className={`ml-auto text-base font-mono ${badge.text}`}>{ind.display}</span>
      </div>

      <div className="space-y-2.5 text-xs">
        <div>
          <span className="text-gray-500">计算方法：</span>
          <span className="text-gray-400 leading-relaxed">{ev.method}</span>
        </div>

        <div>
          <span className="text-gray-500">当日算式：</span>
          <span className="font-mono text-gray-300">{ev.formula}</span>
        </div>

        {inputEntries.length > 0 && (
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {inputEntries.map(([k, v]) => (
              <span key={k} className="text-gray-500">
                {k}：<span className="font-mono text-gray-300">{fmtVal(v)}</span>
              </span>
            ))}
          </div>
        )}

        <div>
          <span className="text-gray-500">判定阈值：</span>
          <span className="text-gray-400">{ev.thresholds}</span>
        </div>

        <div className={`font-medium leading-relaxed ${badge.text}`}>
          判定理由：{ev.reason}
        </div>

        {ev.data_note && (
          <div className="text-amber-400/90 bg-amber-500/10 border border-amber-500/30 rounded px-2.5 py-1.5 leading-relaxed">
            {ev.data_note}
          </div>
        )}

        {ev.window && ev.window.length > 0 && ev.window_stats && (
          <div>
            <div className="text-gray-500 mb-1 leading-relaxed">
              滚动窗口（{ev.window_stats.count} 个交易日，最右为当日）：
              最低 <span className="font-mono text-gray-300">{ev.window_stats.min}</span> ·
              最高 <span className="font-mono text-gray-300">{ev.window_stats.max}</span> ·
              低于当日 <span className="font-mono text-gray-300">{ev.window_stats.below}</span> 天 ·
              相等 <span className="font-mono text-gray-300">{ev.window_stats.equal}</span> 天
            </div>
            <WindowSparkline window={ev.window} />
          </div>
        )}
      </div>
    </div>
  )
}
