import { useMemo, useState, useEffect, useCallback } from 'react'
import { useDerivatives, useRefreshDerivatives } from '../hooks/useDerivatives'
import useIsMobile from '../hooks/useIsMobile'
import SentimentLineChart from '../components/sentiment/SentimentLineChart'
import DivergenceSignals from '../components/derivatives/DivergenceSignals'
import type { OptionPCRPoint, FuturesBasisPoint } from '../api/types'

const PCR_COLORS: Record<string, string> = {
  '510050': '#3b82f6',
  '510300': '#f59e0b',
  '510500': '#a855f7',
  '588000': '#22c55e',
}

const BASIS_COLORS: Record<string, string> = {
  IF: '#3b82f6',
  IC: '#f59e0b',
  IH: '#a855f7',
}

function StatCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-2">{title}</div>
      {children}
    </div>
  )
}

function buildPcrSeries(pcr: OptionPCRPoint[]) {
  const dateSet = new Set<string>()
  const byCode = new Map<string, Map<string, number>>()

  for (const row of pcr) {
    dateSet.add(row.date)
    if (!byCode.has(row.underlying_code)) {
      byCode.set(row.underlying_code, new Map())
    }
    byCode.get(row.underlying_code)!.set(row.date, row.pcr)
  }

  const dates = Array.from(dateSet).sort()
  const lines = Array.from(byCode.entries()).map(([code, dateMap]) => {
    const vals = dates.map(d => dateMap.get(d) ?? null)
    const delta = vals.map((v, i) => {
      if (v == null) return null
      const prev = i >= 5 ? vals[i - 5] : null
      return prev != null ? round4(v - prev) : null
    })
    return {
      name: code === '510050' ? '50ETF' : code === '510300' ? '300ETF' : code === '510500' ? '500ETF' : '科创50ETF',
      data: delta,
      color: PCR_COLORS[code] ?? '#6b7280',
      width: code === '510300' ? 2 : 1.2,
    }
  })

  return { dates, lines }
}

function buildBasisSeries(basis: FuturesBasisPoint[]) {
  const dateSet = new Set<string>()
  const byCode = new Map<string, Map<string, number>>()

  for (const row of basis) {
    dateSet.add(row.date)
    if (!byCode.has(row.futures_code)) {
      byCode.set(row.futures_code, new Map())
    }
    byCode.get(row.futures_code)!.set(row.date, row.basis_pct)
  }

  const dates = Array.from(dateSet).sort()
  const lines = Array.from(byCode.entries()).map(([code, dateMap]) => {
    const vals = dates.map(d => dateMap.get(d) ?? null)
    const delta = vals.map((v, i) => {
      if (v == null) return null
      const prev = i >= 5 ? vals[i - 5] : null
      return prev != null ? round4(v - prev) : null
    })
    return {
      name: code === 'IF' ? 'IF(沪深300)' : code === 'IC' ? 'IC(中证500)' : 'IH(上证50)',
      data: delta,
      color: BASIS_COLORS[code] ?? '#6b7280',
      width: 1.5,
    }
  })

  return { dates, lines }
}

function round4(v: number): number {
  return Math.round(v * 10000) / 10000
}

function latestPcrByCode(pcr: OptionPCRPoint[]): Map<string, { date: string; pcr: number; name: string; delta5: number | null }> {
  const byCode = new Map<string, { date: string; pcr: number; name: string }>()
  const history = new Map<string, Array<{ date: string; pcr: number }>>()

  for (const row of pcr) {
    const prev = byCode.get(row.underlying_code)
    if (!prev || row.date > prev.date) {
      byCode.set(row.underlying_code, { date: row.date, pcr: row.pcr, name: row.underlying_name })
    }
    if (!history.has(row.underlying_code)) history.set(row.underlying_code, [])
    history.get(row.underlying_code)!.push({ date: row.date, pcr: row.pcr })
  }

  const result = new Map<string, { date: string; pcr: number; name: string; delta5: number | null }>()
  for (const [code, latest] of byCode) {
    const hist = (history.get(code) ?? []).sort((a, b) => a.date.localeCompare(b.date))
    const idx = hist.findIndex(h => h.date === latest.date)
    const prev5 = idx >= 5 ? hist[idx - 5] : null
    const delta5 = prev5 ? round4(latest.pcr - prev5.pcr) : null
    const shortName = code === '510050' ? '上证50ETF' : code === '510300' ? '沪深300ETF' : code === '510500' ? '中证500ETF' : '科创50ETF'
    result.set(code, { ...latest, name: shortName, delta5 })
  }
  return result
}

function pcrDeltaZone(delta: number | null): { label: string; color: string } {
  if (delta == null) return { label: '-', color: 'text-gray-500' }
  if (delta >= 0.15) return { label: '恐慌飙升', color: 'text-red-400' }
  if (delta >= 0.05) return { label: '恐慌升温', color: 'text-amber-400' }
  if (delta >= -0.05) return { label: '平稳', color: 'text-gray-300' }
  if (delta >= -0.15) return { label: '情绪回暖', color: 'text-green-400' }
  return { label: '过度乐观', color: 'text-green-400' }
}

function latestBasisByCode(basis: FuturesBasisPoint[]): Map<string, { date: string; basis_pct: number; basis: number; name: string; delta5: number | null }> {
  const byCode = new Map<string, { date: string; basis_pct: number; basis: number; name: string }>()
  const history = new Map<string, Array<{ date: string; basis_pct: number }>>()

  for (const row of basis) {
    const prev = byCode.get(row.futures_code)
    if (!prev || row.date > prev.date) {
      byCode.set(row.futures_code, { date: row.date, basis_pct: row.basis_pct, basis: row.basis, name: row.futures_name })
    }
    if (!history.has(row.futures_code)) history.set(row.futures_code, [])
    history.get(row.futures_code)!.push({ date: row.date, basis_pct: row.basis_pct })
  }

  const result = new Map<string, { date: string; basis_pct: number; basis: number; name: string; delta5: number | null }>()
  for (const [code, latest] of byCode) {
    const hist = (history.get(code) ?? []).sort((a, b) => a.date.localeCompare(b.date))
    const idx = hist.findIndex(h => h.date === latest.date)
    const prev5 = idx >= 5 ? hist[idx - 5] : null
    const delta5 = prev5 ? round4(latest.basis_pct - prev5.basis_pct) : null
    result.set(code, { ...latest, delta5 })
  }
  return result
}

function basisDeltaZone(delta: number | null): { label: string; color: string } {
  if (delta == null) return { label: '-', color: 'text-gray-500' }
  if (delta >= 0.3) return { label: '快速收敛', color: 'text-red-400' }
  if (delta >= 0.05) return { label: '温和改善', color: 'text-amber-400' }
  if (delta >= -0.05) return { label: '平稳', color: 'text-gray-300' }
  return { label: '贴水加深', color: 'text-green-400' }
}

export default function Derivatives() {
  const { data, isLoading, error, refetch } = useDerivatives()
  const refresh = useRefreshDerivatives()
  const isMobile = useIsMobile()
  const [polling, setPolling] = useState(false)

  const handleRefresh = useCallback(() => {
    refresh.mutate()
    setPolling(true)
  }, [refresh])

  useEffect(() => {
    if (!polling) return
    const timer = setInterval(() => refetch(), 5000)
    const stop = setTimeout(() => setPolling(false), 180_000)
    return () => { clearInterval(timer); clearTimeout(stop) }
  }, [polling, refetch])

  const pcrSeries = useMemo(() => data ? buildPcrSeries(data.pcr) : null, [data])
  const basisSeries = useMemo(() => data ? buildBasisSeries(data.basis) : null, [data])
  const pcrLatest = useMemo(() => data ? latestPcrByCode(data.pcr) : null, [data])
  const basisLatest = useMemo(() => data ? latestBasisByCode(data.basis) : null, [data])

  if (error) {
    return <div className="text-red-400 text-center py-20">连接后端失败，请确认服务已启动</div>
  }
  if (isLoading || !data) {
    return <div className="text-gray-400 text-center py-20">加载中...</div>
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <h2 className="text-xl font-bold text-white">衍生品数据</h2>
        <span className="text-xs text-gray-500">期权PCR · 股指期货基差</span>
        <div className="ml-auto flex items-center gap-2">
          {refresh.isSuccess && refresh.data && (
            <span className="text-xs text-gray-500">
              PCR {refresh.data.pcr}行 / 基差 {refresh.data.basis}行
            </span>
          )}
          <button
            onClick={handleRefresh}
            disabled={refresh.isPending || polling}
            className="px-3 py-1.5 rounded text-sm bg-gray-800 text-gray-200 border border-gray-700 hover:border-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {polling ? '拉取中…' : refresh.isPending ? '提交中…' : '手动拉取'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-4 mb-6">
        {pcrLatest && Array.from(pcrLatest.entries()).map(([code, v]) => {
          const zone = pcrDeltaZone(v.delta5)
          const shortName = code === '510050' ? '50ETF' : code === '510300' ? '300ETF' : code === '510500' ? '500ETF' : '科创50'
          return (
            <StatCard key={code} title={`PCR · ${shortName}`}>
              <div className={`text-2xl font-mono ${v.delta5 != null && v.delta5 >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                {v.delta5 != null ? `${v.delta5 > 0 ? '+' : ''}${v.delta5.toFixed(3)}` : '-'}
              </div>
              <div className={`mt-1 text-xs ${zone.color}`}>{zone.label}</div>
              <div className="text-[10px] text-gray-600 mt-1">5日变化 · {v.date}</div>
            </StatCard>
          )
        })}
        {basisLatest && Array.from(basisLatest.entries()).map(([code, v]) => {
          const zone = basisDeltaZone(v.delta5)
          return (
            <StatCard key={code} title={`基差 · ${code}`}>
              <div className={`text-2xl font-mono ${v.delta5 != null && v.delta5 >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                {v.delta5 != null ? `${v.delta5 > 0 ? '+' : ''}${v.delta5.toFixed(3)}%` : '-'}
              </div>
              <div className={`mt-1 text-xs ${zone.color}`}>{zone.label}</div>
              <div className="text-[10px] text-gray-600 mt-1">5日变化 · {v.date}</div>
            </StatCard>
          )
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-300 mb-2">期权PCR 5日变化</div>
          {pcrSeries && pcrSeries.dates.length > 0 ? (
            <SentimentLineChart
              dates={pcrSeries.dates}
              height={isMobile ? 240 : 340}
              yFormatter={v => v.toFixed(2)}
              lineTip={v => `${v > 0 ? '+' : ''}${v.toFixed(3)}`}
              lines={pcrSeries.lines}
            />
          ) : (
            <div className="text-gray-500 text-center py-10">暂无PCR数据</div>
          )}
          <div className="mt-2 text-xs text-gray-600 leading-relaxed">
            <p className="mb-1"><span className="text-gray-400">怎么看：</span>图中显示 PCR 的 5 日变化量。PCR = 认沽成交量 ÷ 认购成交量。</p>
            <p className="mb-1">不同标的 PCR 中枢差异大(50ETF 约 0.7，科创50 约 1.1)，绝对值无法横向比较；
              但<span className="text-gray-400">变化方向</span>含义一致：</p>
            <p>· PCR 急升(线向上) → 恐慌加剧，买保险的人骤增 → <span className="text-red-400">底部信号</span></p>
            <p>· PCR 急降(线向下) → 过度乐观，投机情绪升温 → <span className="text-green-400">顶部警告</span></p>
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-300 mb-2">股指期货基差 5 日变化(bp)</div>
          {basisSeries && basisSeries.dates.length > 0 ? (
            <SentimentLineChart
              dates={basisSeries.dates}
              height={isMobile ? 240 : 340}
              yFormatter={v => v.toFixed(2)}
              lineTip={v => `${v > 0 ? '+' : ''}${v.toFixed(3)}%`}
              lines={basisSeries.lines}
            />
          ) : (
            <div className="text-gray-500 text-center py-10">暂无基差数据</div>
          )}
          <div className="mt-2 text-xs text-gray-600 leading-relaxed">
            <p className="mb-1"><span className="text-gray-400">怎么看：</span>图中显示的是基差率的 5 个交易日变化量，而非绝对值。</p>
            <p className="mb-1">A 股股指期货(IC/IF/IH)长期存在结构性贴水，绝对基差率与大盘走势关联弱；
              但<span className="text-gray-400">基差的变化速度</span>包含有效信号：</p>
            <p>· 贴水快速收敛(线向上) → 机构恐慌缓解，常出现在底部确认阶段</p>
            <p>· 贴水突然加深(线向下) → 机构加速对冲，往往领先于现货下跌</p>
            <p>· IC 贴水最深(对冲需求最大)，IF/IH 相对浅</p>
          </div>
        </div>
      </div>

      <DivergenceSignals />

      <p className="mt-4 text-xs text-gray-600">
        数据来源: 上交所期权每日统计 + 新浪财经股指期货主力合约。PCR 为上交所ETF期权认沽/认购成交量比;
        基差为IF/IC/IH主力合约收盘价与对应现货指数收盘价之差。
      </p>
    </div>
  )
}
