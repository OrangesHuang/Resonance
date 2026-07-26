import * as echarts from 'echarts'
import type { EChartsType } from 'echarts'
import { useSentiment, useRefreshSentiment } from '../hooks/useSentiment'
import SentimentLineChart from '../components/SentimentLineChart'
import type { VolumeState, ZoneKey, ZoneLevel, ZoneIndicator, SentimentZone } from '../api/types'

function formatYi(v: number | null | undefined): string {
  if (v == null) return '-'
  const abs = Math.abs(v)
  if (abs >= 10000) return `${(v / 10000).toFixed(4)} 万亿`
  return `${v.toFixed(0)} 亿`
}

function formatSignedYi(v: number | null | undefined): string {
  if (v == null) return '-'
  const sign = v > 0 ? '+' : ''
  return `${sign}${formatYi(v)}`
}

const CHART_GROUP = 'sentiment-linked'

function linkChart(instance: EChartsType) {
  instance.group = CHART_GROUP
  echarts.connect(CHART_GROUP)
}

const VOLUME_STATE_STYLES: Record<VolumeState, string> = {
  放量: 'bg-red-500/20 text-red-400',
  缩量: 'bg-green-500/20 text-green-400',
  持平: 'bg-gray-700/40 text-gray-300',
}

function StatCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-2">{title}</div>
      {children}
    </div>
  )
}

const ZONE_STYLES: Record<ZoneKey, { card: string; text: string }> = {
  danger: { card: 'border-red-500/40 bg-red-500/10', text: 'text-red-400' },
  neutral: { card: 'border-amber-500/40 bg-amber-500/10', text: 'text-amber-400' },
  safe: { card: 'border-green-500/40 bg-green-500/10', text: 'text-green-400' },
}

const LEVEL_LABEL: Record<ZoneLevel, string> = { high: '过热', mid: '中性', low: '冷清' }

const LEVEL_STYLES: Record<ZoneLevel, string> = {
  high: 'bg-red-500/20 text-red-400',
  mid: 'bg-gray-700/40 text-gray-300',
  low: 'bg-green-500/20 text-green-400',
}

function ZoneIndicatorItem({ name, ind }: { name: string; ind: ZoneIndicator }) {
  return (
    <div>
      <div className="text-xs text-gray-400 mb-1">{name}</div>
      <div className="flex items-center gap-2">
        <span className="text-lg font-mono text-white">{ind.percentile.toFixed(0)}%</span>
        <span className="text-xs text-gray-500">分位</span>
        <span className={`px-2 py-0.5 rounded text-xs ${LEVEL_STYLES[ind.level]}`}>{LEVEL_LABEL[ind.level]}</span>
      </div>
    </div>
  )
}

function ZoneBanner({ zone }: { zone: SentimentZone }) {
  const cur = zone.current
  if (!cur) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6 text-sm text-gray-500">
        历史数据不足，暂无法判断情绪分区
      </div>
    )
  }
  const zs = ZONE_STYLES[cur.zone]
  return (
    <div className={`border rounded-lg p-4 mb-6 ${zs.card}`}>
      <div className="flex items-center gap-6 flex-wrap">
        <div>
          <div className="text-xs text-gray-400 mb-1">当前情绪分区 · {cur.date}</div>
          <div className="flex items-center gap-3">
            <span className={`text-2xl font-bold ${zs.text}`}>{cur.label}</span>
            <span className="text-xs text-gray-400 font-mono">
              情绪分 {cur.score > 0 ? `+${cur.score}` : cur.score}
            </span>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-8 flex-wrap">
          <ZoneIndicatorItem name="成交额 (MA5平滑)" ind={cur.turnover} />
          <ZoneIndicatorItem name="融资余额" ind={cur.margin} />
        </div>
      </div>
      <div className="mt-3 text-xs text-gray-500 leading-relaxed">
        按近 {cur.window} 个交易日滚动分位数划分：成交额与融资余额各自 ≥80 分位记为过热、≤20 分位记为冷清，
        两者打分(过热+1/冷清-1)求和 ≥1 为危险区、≤-1 为安全区、其余为中性区。
      </div>
    </div>
  )
}

export default function Sentiment() {
  const { data, isLoading, error } = useSentiment()
  const refresh = useRefreshSentiment()

  if (error) {
    return <div className="text-red-400 text-center py-20">连接后端失败，请确认服务已启动</div>
  }
  if (isLoading || !data) {
    return <div className="text-gray-400 text-center py-20">加载中...</div>
  }

  const tSum = data.summary.turnover
  const mSum = data.summary.margin

  const dates = data.turnover.map(p => p.date)
  const marginByDate = new Map(data.margin.map(p => [p.date, p]))
  const zoneByDate = new Map(data.zone.history.map(p => [p.date, p]))
  const marginLine = dates.map(d => marginByDate.get(d)?.fin_balance_yi ?? null)
  const marginBar = dates.map(d => marginByDate.get(d)?.net_fin_buy_yi ?? null)
  const zoneBar = dates.map(d => zoneByDate.get(d)?.score ?? null)

  const netBuy = mSum?.net_fin_buy_yi ?? null
  const netBuyColor = netBuy == null ? 'text-gray-400' : netBuy >= 0 ? 'text-red-400' : 'text-green-400'

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-xl font-bold text-white">市场情绪</h2>
        {data.updated_at && (
          <span className="text-xs text-gray-500">数据截至 {data.updated_at}</span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {refresh.isSuccess && refresh.data && (
            <span className="text-xs text-gray-500">
              已更新 成交额{refresh.data.turnover_days}天 / 两融{refresh.data.margin_days}天
            </span>
          )}
          <button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            className="px-3 py-1.5 rounded text-sm bg-gray-800 text-gray-200 border border-gray-700 hover:border-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {refresh.isPending ? '拉取中…' : '手动拉取'}
          </button>
        </div>
      </div>

      <ZoneBanner zone={data.zone} />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <StatCard title="两市成交额">
          <div className="text-2xl font-mono text-white">{formatYi(tSum?.latest_yi)}</div>
          <div className="mt-1 text-xs text-gray-500">MA5 {formatYi(tSum?.ma5_yi)}</div>
        </StatCard>
        <StatCard title="量能状态">
          {tSum?.volume_state ? (
            <span className={`inline-block px-2 py-1 rounded text-sm font-medium ${VOLUME_STATE_STYLES[tSum.volume_state]}`}>
              {tSum.volume_state}
            </span>
          ) : (
            <span className="text-gray-500">-</span>
          )}
          <div className="mt-2 text-xs text-gray-500 font-mono">
            量比 {tSum?.vol_ratio != null ? tSum.vol_ratio.toFixed(2) : '-'}
          </div>
        </StatCard>
        <StatCard title="融资余额">
          <div className="text-2xl font-mono text-white">{formatYi(mSum?.fin_balance_yi)}</div>
          <div className="mt-1 text-xs text-gray-500">两融杠杆资金</div>
        </StatCard>
        <StatCard title="融资净买入(近似)">
          <div className={`text-2xl font-mono ${netBuyColor}`}>{formatSignedYi(netBuy)}</div>
          <div className="mt-1 text-xs text-gray-500">较上一交易日</div>
        </StatCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-300 mb-2">两市成交额(万亿)</div>
          <SentimentLineChart
            dates={dates}
            height={340}
            yFormatter={v => (v / 10000).toFixed(4)}
            lineTip={v => `${(v / 10000).toFixed(4)} 万亿`}
            onReady={linkChart}
            lines={[
              { name: '成交额', data: data.turnover.map(p => p.total_amount_yi), color: '#3b82f6', width: 1.5 },
              { name: 'MA5', data: data.turnover.map(p => p.ma5_yi), color: '#f59e0b', width: 1.2 },
            ]}
          />
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-300 mb-2">融资余额(万亿) · 净买入(亿)</div>
          <SentimentLineChart
            dates={dates}
            height={340}
            yFormatter={v => (v / 10000).toFixed(4)}
            lineTip={v => `${(v / 10000).toFixed(4)} 万亿`}
            barFormatter={v => v.toFixed(0)}
            onReady={linkChart}
            lines={[
              { name: '融资余额', data: marginLine, color: '#a855f7', width: 1.5 },
            ]}
            bars={{
              name: '净买入',
              data: marginBar,
              colorFor: v => (v >= 0 ? '#ef4444' : '#22c55e'),
            }}
          />
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mt-6">
        <div className="text-sm font-medium text-gray-300 mb-2">情绪分区历史（红=危险区 · 绿=安全区 · 灰=中性区）</div>
        <SentimentLineChart
          dates={dates}
          height={220}
          barFormatter={v => v.toFixed(0)}
          onReady={linkChart}
          lines={[]}
          bars={{
            name: '情绪分',
            data: zoneBar,
            colorFor: v => (v >= 1 ? '#ef4444' : v <= -1 ? '#22c55e' : '#4b5563'),
          }}
          barTip={v => (v >= 1 ? '危险区' : v <= -1 ? '安全区' : '中性区')}
        />
      </div>

      <p className="mt-4 text-xs text-gray-600">
        注: 融资净买入为融资余额相邻交易日差分近似值; 成交额为上交所(上证指数)与深交所(深证综指)合计。
      </p>
    </div>
  )
}
