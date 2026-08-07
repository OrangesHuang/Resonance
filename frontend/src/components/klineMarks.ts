import type { KlinePoint, TradePoint } from '../api/types'

interface Marks {
  markPoint: object
  markLine: object
  markLineTop: object
  probMarkLine: object
}

/** 构建K线标记: 买卖点/选中日期线/概率分界线(始终定义, 数据为空即清除)。 */
export function buildMarks(trades: TradePoint[], kline: KlinePoint[],
                           dates: string[], selectedDate: string | null): Marks {
  const klineByDate = new Map(kline.map(k => [k.date, k]))
  const tradeMarks = trades
    .filter(t => klineByDate.has(t.date))
    .map(t => {
      const k = klineByDate.get(t.date)!
      const isBuy = t.action === 'BUY'
      return {
        coord: [t.date, isBuy ? k.low * 0.995 : k.high * 1.005],
        value: isBuy ? 'B' : 'S',
        symbol: isBuy ? 'triangle' : 'pin',
        symbolSize: isBuy ? 22 : 24,
        symbolRotate: isBuy ? 0 : 180,
        itemStyle: { color: isBuy ? '#15803d' : '#ef4444' },
        label: { show: true, formatter: isBuy ? '买' : '卖', fontSize: 11, color: '#fff', offset: [0, isBuy ? 5 : -5] as [number, number] },
        _reason: `${t.date} ${isBuy ? '买入' : '卖出'} @${t.price}\n${t.reason}`,
      }
    })
  const markPoint = {
    clip: false,
    data: tradeMarks,
    tooltip: {
      formatter: (p: { data?: { _reason?: string } }) =>
        (p.data?._reason ?? '').replace('\n', '<br/>'),
    },
  }

  const showMarkLine = selectedDate !== null && dates.includes(selectedDate)
  const baseMarkLine = {
    silent: true,
    symbol: 'none',
    lineStyle: { color: '#38bdf8', type: 'dashed' as const, width: 1 },
    label: { show: false },
  }
  const markLine = showMarkLine
    ? { ...baseMarkLine, data: [{ xAxis: selectedDate }] }
    : { ...baseMarkLine, data: [] }
  const markLineTop = showMarkLine
    ? { ...markLine, label: { show: true, formatter: selectedDate ?? '', color: '#38bdf8', fontSize: 10, position: 'insideEndTop' as const } }
    : markLine

  const probMarkLine = {
    silent: true,
    symbol: 'none',
    label: { fontSize: 9 },
    data: [
      { yAxis: 70, lineStyle: { color: '#ef4444', type: 'dashed' }, label: { formatter: 'HIGH 70%', color: '#ef4444' } },
      { yAxis: 50, lineStyle: { color: '#f59e0b', type: 'dashed' }, label: { formatter: 'MID 50%', color: '#f59e0b' } },
      ...(showMarkLine
        ? [{ xAxis: selectedDate, lineStyle: { color: '#38bdf8', type: 'dashed' }, label: { show: false } }]
        : []),
    ],
  }
  return { markPoint, markLine, markLineTop, probMarkLine }
}
