import { Link } from 'react-router-dom'
import { useSentiment } from '../../hooks/useSentiment'
import useIsMobile from '../../hooks/useIsMobile'
import { useChartSync, SENTIMENT_SYNC_GROUP } from '../../hooks/useChartSync'
import { useAxisPointerBridge } from '../../hooks/useAxisPointerBridge'
import type { DateWindow } from '../common/chartZoom'
import type { ZoneKey } from '../../api/types'
import SentimentLineChart from '../sentiment/SentimentLineChart'

const ZONE_TEXT: Record<ZoneKey, string> = {
  danger: 'text-red-400',
  neutral: 'text-amber-400',
  safe: 'text-green-400',
}

/** 共振页底部市场情绪区: 成交额/融资两图 + 情绪分区概览（与情绪页共用数据源）。 */
export default function MarketSentimentSection({ selectedDate, bridge, onSelectDate, dateWindow, onZoomChange, alignDates }: {
  selectedDate: string | null
  bridge: ReturnType<typeof useAxisPointerBridge>
  onSelectDate: (date: string) => void
  dateWindow: DateWindow | null
  onZoomChange: (w: DateWindow) => void
  // 五图统一日期轴(K线 ∪ 共振历史): 情绪数据缺失的日期补 null,
  // 保证缩放百分比窗口与 K线/红绿灯/热力图逐日对齐
  alignDates: string[]
}) {
  const { data, isLoading, error } = useSentiment()
  const isMobile = useIsMobile()
  const onSentimentReady = useChartSync(SENTIMENT_SYNC_GROUP)

  if (error) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg py-6 text-center text-xs text-gray-600">
        情绪数据加载失败
      </div>
    )
  }
  if (isLoading || !data) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg py-10 text-center text-sm text-gray-500">
        情绪数据加载中...
      </div>
    )
  }

  const turnoverByDate = new Map(data.turnover.map(p => [p.date, p]))
  const marginByDate = new Map(data.margin.map(p => [p.date, p]))
  const dates = alignDates
  const turnoverAmount = dates.map(d => turnoverByDate.get(d)?.total_amount_yi ?? null)
  const turnoverMa5 = dates.map(d => turnoverByDate.get(d)?.ma5_yi ?? null)
  const marginLine = dates.map(d => marginByDate.get(d)?.fin_balance_yi ?? null)
  const marginBar = dates.map(d => marginByDate.get(d)?.net_fin_buy_yi ?? null)
  const cur = data.zone.current

  return (
    <div>
      <div className="flex items-center gap-3 mb-2 flex-wrap">
        <h3 className="text-sm font-medium text-gray-300">市场情绪走势（成交额热度 / 融资杠杆两灯的底层数据）</h3>
        {cur && (
          <span className="text-xs text-gray-500">
            情绪分区 <b className={ZONE_TEXT[cur.zone]}>{cur.label}</b>
            · 成交额 {cur.turnover.percentile.toFixed(0)}% 分位
            · 融资 {cur.margin.percentile.toFixed(0)}% 分位
          </span>
        )}
        <Link to="/sentiment" className="ml-auto text-xs text-gray-500 hover:text-gray-300 transition-colors">
          查看详情 →
        </Link>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-500 mb-1">两市成交额(万亿) · MA5</div>
          <SentimentLineChart
            dates={dates}
            height={isMobile ? 180 : 240}
            yFormatter={v => (v / 10000).toFixed(4)}
            lineTip={v => (v / 10000).toFixed(4) + ' 万亿'}
            selectedDate={selectedDate}
            bridge={bridge}
            onSelectDate={onSelectDate}
            dateWindow={dateWindow}
            onZoomChange={onZoomChange}
            onReady={onSentimentReady}
            lines={[
              { name: '成交额', data: turnoverAmount, color: '#3b82f6', width: 1.5 },
              { name: 'MA5', data: turnoverMa5, color: '#f59e0b', width: 1.2 },
            ]}
          />
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-500 mb-1">融资余额(万亿) · 净买入(亿)</div>
          <SentimentLineChart
            dates={dates}
            height={isMobile ? 180 : 240}
            yFormatter={v => (v / 10000).toFixed(4)}
            lineTip={v => (v / 10000).toFixed(4) + ' 万亿'}
            barFormatter={v => v.toFixed(0)}
            selectedDate={selectedDate}
            bridge={bridge}
            onSelectDate={onSelectDate}
            dateWindow={dateWindow}
            onZoomChange={onZoomChange}
            onReady={onSentimentReady}
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
    </div>
  )
}