import ResonanceKline from './ResonanceKline'
import KlineIndicatorGuide from './KlineIndicatorGuide'
import type { KlinePoint, ResonanceHistoryPoint, DailySignal, TradePoint } from '../../api/types'
import type { AxisPointerBridge } from '../../hooks/useAxisPointerBridge'
import type { DateWindow } from '../common/chartZoom'

interface Props {
  code: string
  kline: KlinePoint[]
  history: ResonanceHistoryPoint[]
  signals: DailySignal[]
  trades: TradePoint[]
  selectedDate: string | null
  onSelectDate: (date: string) => void
  dateWindow: DateWindow | null
  onZoomChange: (w: DateWindow) => void
  bridge: AxisPointerBridge
  loaded: boolean
}

export default function KlineSection({
  code, kline, history, signals, trades, selectedDate, onSelectDate, dateWindow, onZoomChange, bridge, loaded,
}: Props) {
  return (
    <>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center gap-3 mb-2 flex-wrap">
          <h3 className="text-sm font-medium text-gray-300">K线走势（点击K线查看当日依据）</h3>
          <span className="text-[11px] text-gray-600">悬停查看各项数值 · 各副图指标含义见下方「K线副图指标说明」</span>
        </div>
        {loaded ? (
          <ResonanceKline
            key={code}
            kline={kline}
            history={history}
            signals={signals}
            trades={trades}
            selectedDate={selectedDate}
            onSelectDate={onSelectDate}
            dateWindow={dateWindow}
            onZoomChange={onZoomChange}
            bridge={bridge}
          />
        ) : (
          <div className="text-gray-500 text-center py-16">K线加载中...</div>
        )}
      </div>

      <KlineIndicatorGuide />
    </>
  )
}
