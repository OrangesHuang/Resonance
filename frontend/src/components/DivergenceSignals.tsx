import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchDivergenceSignals } from '../api/client'
import type { DivergenceSignal } from '../api/types'

const MAX_ROWS = 15

const RULE_DESC: Record<string, string> = {
  R1: '涨势中基差贴水加深 = 机构边涨边对冲',
  R3: '涨势中恐慌盘骤撤 = 情绪过热',
  R5: '20日新高但PCR低分位 = 无人恐慌',
  R5b: '加速新高+情绪极冷 = 逼空赶顶(强)',
  R7: '新高但基差无对冲 = 纯散户行情(弱)',
  R8: '涨势中基差深度贴水 = 机构边涨边空',
  R2: '跌势中基差快速收窄 = 机构回补',
  R4: '跌势中PCR骤升 = 恐慌升温',
  R6: '20日新低但PCR高分位 = 恐慌',
  R9: '止跌回升+基差急收窄 = 机构回补确认(强)',
  R10: '恐慌极点+价格企稳 = 空头耗尽(强)',
}

function SignalRow({ s }: { s: DivergenceSignal }) {
  const isTop = s.kind === 'TOP'
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-gray-800/60 last:border-0 text-sm">
      <span className="text-gray-500 font-mono text-xs w-24 shrink-0">{s.date}</span>
      <span
        className={`w-10 text-center text-xs font-bold rounded px-1 py-0.5 shrink-0 ${
          isTop ? 'bg-red-500/15 text-red-400' : 'bg-green-500/15 text-green-400'
        }`}
      >
        {isTop ? '顶' : '底'}
      </span>
      <span
        className={`text-[10px] rounded px-1 py-0.5 shrink-0 ${
          s.grade === 'CONF' ? 'bg-amber-500/15 text-amber-400' : 'bg-gray-700/40 text-gray-400'
        }`}
        title={s.grade === 'CONF' ? '含机构(基差)证据, 可信度高' : '纯情绪(PCR)证据, 需价格确认'}
      >
        {s.grade === 'CONF' ? '确认' : '观察'}
      </span>
      <span className="font-mono text-xs text-gray-300 w-16 shrink-0">{s.close.toFixed(3)}</span>
      <span className="text-[10px] text-gray-500 truncate">
        {s.rule_names.map(r => `[${r}]`).join('')}
      </span>
    </div>
  )
}

export default function DivergenceSignals() {
  const [showExplain, setShowExplain] = useState(false)
  const { data, isLoading } = useQuery({
    queryKey: ['derivatives', 'divergence'],
    queryFn: () => fetchDivergenceSignals('588000'),
    refetchInterval: false,
    refetchOnWindowFocus: false,
  })

  const signals = data?.signals ?? []
  const latest = signals.slice(-MAX_ROWS).reverse()
  const confCount = signals.filter(s => s.grade === 'CONF').length

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mt-6">
      <div className="flex items-center gap-3 mb-1 flex-wrap">
        <div className="text-sm font-medium text-gray-300">三维背离信号 · 科创50ETF(588000)</div>
        <span className="text-[10px] text-gray-600">
          K线 + 期权PCR + IC基差(代理) · 历史{signals.length}条信号({confCount}确认)
        </span>
        <button
          onClick={() => setShowExplain(v => !v)}
          className="ml-auto text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          {showExplain ? '收起算法说明 ▲' : '算法怎么看 ▼'}
        </button>
      </div>

      {showExplain && (
        <div className="mt-3 text-xs text-gray-500 leading-relaxed bg-gray-950/60 rounded-lg p-3 space-y-2">
          <p>
            <span className="text-gray-400">核心框架：</span>市场由三类参与者构成——趋势跟随者(价格)、机构(股指期货基差)、
            散户/对冲者(期权PCR)。<span className="text-gray-300">价格定方向，衍生品定背离</span>：
            价格创新高但机构在加对冲、散户毫无恐惧 → 顶；价格创新低但机构在回补、散户极度恐慌 → 底。
            单看任何单一指标都会被骗(如 2026-06-30 大顶时 PCR=1.124 反而是"底部"读数)，背离共振才有效。
          </p>
          <p>
            <span className="text-gray-400">为什么看 5 日变化率：</span>IC 基差常年结构性贴水(-1%~-3%)，
            PCR 各标的有天然基线(50ETF≈0.7，科创50≈1.1)，绝对值无法横向比较；
            变化方向(一阶导)才是标准化信号。IC 为科创50 的代理基差(科创50 无对应股指期货)。
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1">
            <div>
              <p className="text-amber-400/80 mb-0.5">顶部规则(分数≥2.0 且价格处20日高位)</p>
              {Object.entries(RULE_DESC).filter(([r]) => !['R2', 'R4', 'R6', 'R9', 'R10'].includes(r))
                .map(([r, d]) => <p key={r}>· {r} {d}</p>)}
            </div>
            <div>
              <p className="text-green-400/80 mb-0.5">底部规则(分数≥2.0 且价格处20日低位)</p>
              {Object.entries(RULE_DESC).filter(([r]) => ['R2', 'R4', 'R6', 'R9', 'R10'].includes(r))
                .map(([r, d]) => <p key={r}>· {r} {d}</p>)}
            </div>
          </div>
          <p>
            <span className="text-gray-400">信号分级：</span>
            <span className="text-amber-400">确认</span> = 含机构(基差)证据，可信度高；
            <span className="text-gray-300">观察</span> = 纯情绪(PCR)证据，需价格确认。
          </p>
          <p>
            <span className="text-gray-400">已知局限：</span>① 动量耗尽型顶(如 2025-10-09)无先兆背离，
            只提供提前数日的领先信号；② 双顶次高点不重复触发(首次见顶已报警)；
            ③ 阴跌慢底无恐慌信号，由 R9 在反弹确认时补发(+5日)；
            ④ 2024-06-26 前无 PCR 数据，算法退化为"基差+价格"二维。
          </p>
        </div>
      )}

      <div className="mt-2">
        {isLoading && <div className="text-gray-500 text-center py-6 text-sm">加载信号中...</div>}
        {!isLoading && latest.length === 0 && (
          <div className="text-gray-500 text-center py-6 text-sm">暂无信号(数据不足或需先拉取衍生品数据)</div>
        )}
        {latest.map(s => <SignalRow key={s.date + s.kind} s={s} />)}
      </div>
    </div>
  )
}
