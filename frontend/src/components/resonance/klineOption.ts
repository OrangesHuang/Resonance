import type { EChartsOption } from 'echarts'
import type { TooltipComponentOption } from 'echarts/components'
import type { KlinePoint, ResonanceHistoryPoint, DailySignal, TradePoint, DangerZone } from '../../api/types'
import { buildTradeBands, sanitizeBands } from '../kline/tradeBands'
import { buildKlineTooltip } from '../kline/klineTooltip'
import { buildMarks } from '../kline/klineMarks'
import type { RangeSelection } from '../kline/rangeSelect'
import type { RangeStats } from '../kline/rangeStats'

const AXIS_LABEL = '#6b7280'
const DANGER_BAND = 'rgba(239, 68, 68, 0.08)'
const CHANCE_BAND = 'rgba(34, 197, 94, 0.08)'
const DANGER_ZONE_COLOR = 'rgba(239, 68, 68, 0.16)' // 危险区(首买点前无买点段), 深于普通空仓带
const UP_COLOR = '#ef4444'
const DOWN_COLOR = '#22c55e'

interface BuildParams {
  kline: KlinePoint[]
  history: ResonanceHistoryPoint[]
  signals: DailySignal[]
  trades: TradePoint[]
  dangerZone: DangerZone | null | undefined
  selectedDate: string | null
  rangeSel: { sel: RangeSelection; band: Array<{ xAxis: string; itemStyle?: object }>; mode: boolean }
  rangeStats: RangeStats | null
  isMobile: boolean
}

const BULL_BAND = 'rgba(34, 197, 94, 0.05)'
const BEAR_BAND = 'rgba(239, 68, 68, 0.05)'

function buildRegimeBands(kline: KlinePoint[], dates: string[]): Array<Array<{ xAxis: string; itemStyle?: object }>> {
  // 牛熊背景带: close >= ma250 为牛(淡绿), close < ma250 为熊(淡红)
  // (ma250 斜率更准, 但需逐点比较; 收盘 vs ma250 是可视化代理)
  const bands: Array<Array<{ xAxis: string; itemStyle?: object }>> = []
  let cur: Array<{ xAxis: string; itemStyle?: object }> = []
  let curState: 'bull' | 'bear' | null = null
  for (let i = 0; i < kline.length; i++) {
    const k = kline[i]
    const m = k.ma250
    if (m == null) continue
    const state: 'bull' | 'bear' = k.close >= m ? 'bull' : 'bear'
    if (state !== curState) {
      if (cur.length >= 2) bands.push(cur)
      cur = [{ xAxis: dates[i], itemStyle: { color: state === 'bull' ? BULL_BAND : BEAR_BAND } }]
      curState = state
    } else {
      cur.push({ xAxis: dates[i] })
    }
  }
  if (cur.length >= 2) bands.push(cur)
  return bands
}

export function buildKlineOption({ kline, history, signals, trades, dangerZone, selectedDate, rangeSel, rangeStats, isMobile }: BuildParams): { option: EChartsOption | null; dates: string[] } {
  if (kline.length === 0) return { option: null, dates: [] }
  const dates = kline.map(k => k.date)
  const ohlc = kline.map(k => [k.open, k.close, k.low, k.high])
  const volumes = kline.map(k => k.volume)

  const sigByDate = new Map<string, DailySignal>()
  for (const s of signals) sigByDate.set(s.date, s)
  const flowData = dates.map(d => {
    const v = sigByDate.get(d)?.shares_delta_yi
    if (v == null) return { value: null, itemStyle: { color: '#374151' } }
    return { value: v, itemStyle: { color: v >= 0 ? DOWN_COLOR : UP_COLOR } }
  })
  const probData = dates.map(d => sigByDate.get(d)?.composite_prob ?? null)

  const bands = sanitizeBands(
    history
      .filter(h => h.red >= 3 || h.green >= 3)
      .map(h => [
        { xAxis: h.date, itemStyle: { color: h.red >= 3 ? DANGER_BAND : CHANCE_BAND } },
        { xAxis: h.date },
      ]),
    dates,
  )

  // 买卖点区间蒙布: 持仓段淡绿 / 空仓段淡红
  const tradeBands = sanitizeBands(buildTradeBands(trades, dates[dates.length - 1]), dates)
  // 危险区蒙布: 策略声明的首买点前无买点段(仅 Beta 类全程策略返回, 正式版无此字段不标)
  const dangerZoneBands = dangerZone
    ? sanitizeBands(
        [
          [
            {
              xAxis: dangerZone.start,
              itemStyle: { color: DANGER_ZONE_COLOR },
              label: { show: true, position: 'insideTop', color: 'rgba(239, 68, 68, 0.85)', fontSize: 10, formatter: dangerZone.label },
            },
            { xAxis: dangerZone.end },
          ],
        ] as never[],
        dates,
      )
    : []
  // 区间统计蒙版: rangeSel.band 是 [首日, 末日] 二元组, 必须整体传入不可展开
  const rangeBand = rangeSel.band.length ? sanitizeBands([rangeSel.band] as never[], dates) : []

  // 区间统计激活: 禁用 inside 拖拽平移(拖拽=框选)
  // 注意: ECharts merge 语义下未显式字段会残留旧值,
  // 关闭时必须显式设回 moveOnMouseMove: true 否则拖移永久失效
  // 移动端: 不使用 brush(触摸不支持), 改用两次点击选区间
  const brushActive = rangeSel.mode && !isMobile
  const insideZoom = brushActive
    ? { type: 'inside' as const, xAxisIndex: [0, 1, 2, 3], moveOnMouseMove: false }
    : { type: 'inside' as const, xAxisIndex: [0, 1, 2, 3], moveOnMouseMove: true, preventDefaultMouseMove: true }

  const { markPoint, markLine, markLineTop, probMarkLine } =
    buildMarks(trades, kline, dates, selectedDate)

  const tradeByDate = new Map(trades.map(t => [t.date, t]))
  const tooltipFormatter = buildKlineTooltip(kline, sigByDate, tradeByDate, rangeStats)

  return {
    option: {
      backgroundColor: 'transparent',
      animation: false,
      // brushType 随 mode 动态化: 激活 rect / 关闭 false
      // (写死 rect 会在关闭后的任何 setOption 时重新激活 brush 占用
      //  globalPan 互斥锁, 导致 dataZoom 拖拽平移失效)
      // 移动端不支持 brush, 改用两次点击选区间
      brush: {
        xAxisIndex: 0,
        yAxisIndex: 0,
        brushType: brushActive ? 'rect' : false,
        brushMode: 'single',
        brushStyle: {
          borderColor: '#0ea5e9',
          color: 'rgba(56, 189, 248, 0.10)',
          borderWidth: 1,
        },
        throttleType: 'debounce',
        throttleDelay: 60,
        removeOnClick: false,
      },
      tooltip: {
        // 默认 transitionDuration 0.4s: 每次悬停 tooltip 会从轴吸附位
        // 平滑漂移到鼠标位(两次定位被 CSS transition 动画化), 逐日查看很乱
        transitionDuration: 0,
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: '#111827',
        borderColor: '#374151',
        textStyle: { color: '#e5e7eb' },
        formatter: tooltipFormatter as TooltipComponentOption['formatter'],
      },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      visualMap: [
        {
          show: false,
          seriesIndex: 3,
          type: 'continuous',
          min: 0,
          max: 100,
          inRange: { color: ['#ef4444', '#f59e0b', '#22c55e'] },
        },
      ],
      grid: [
        { left: 60, right: 20, top: 20, height: '38%' },
        { left: 60, right: 20, top: '59%', height: '6%' },
        { left: 60, right: 20, top: '66%', height: '6%' },
        { left: 60, right: 20, top: '73%', height: '11%' },
      ],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0, boundaryGap: true, axisLabel: { color: AXIS_LABEL, fontSize: 10 } },
        { type: 'category', data: dates, gridIndex: 1, boundaryGap: true, axisLabel: { show: false } },
        { type: 'category', data: dates, gridIndex: 2, boundaryGap: true, axisLabel: { show: false } },
        { type: 'category', data: dates, gridIndex: 3, boundaryGap: false, axisLabel: { show: false } },
      ],
      yAxis: [
        { scale: true, gridIndex: 0, boundaryGap: ['3%', '3%'], splitLine: { lineStyle: { color: '#1f2937' } }, axisLabel: { color: AXIS_LABEL } },
        { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false } },
        { scale: true, gridIndex: 2, splitLine: { show: false }, axisLabel: { color: AXIS_LABEL, fontSize: 9 } },
        { min: 0, max: 100, gridIndex: 3, splitNumber: 2, splitLine: { show: false }, axisLabel: { color: AXIS_LABEL, fontSize: 9, formatter: '{value}%' } },
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: ohlc,
          xAxisIndex: 0,
          yAxisIndex: 0,
          itemStyle: {
            color: UP_COLOR,
            color0: DOWN_COLOR,
            borderColor: UP_COLOR,
            borderColor0: DOWN_COLOR,
          },
          markArea: { silent: true, data: sanitizeBands([...dangerZoneBands, ...bands, ...tradeBands, ...rangeBand] as never[], dates) },
          markLine: markLineTop,
          markPoint,
        },
        {
          name: 'MA250(牛熊线)',
          type: 'line',
          data: kline.map(k => k.ma250 ?? null),
          xAxisIndex: 0,
          yAxisIndex: 0,
          showSymbol: false,
          connectNulls: true,
          silent: true,
          lineStyle: { width: 1.2, color: '#f59e0b', type: 'dashed' },
          // 牛熊区 markArea: 收盘 vs ma250 (ma250 斜率更准, 可视化用代理)
          markArea: { silent: true, data: sanitizeBands(buildRegimeBands(kline, dates) as never[], dates) },
        },
        {
          name: '成交量',
          type: 'bar',
          data: volumes,
          xAxisIndex: 1,
          yAxisIndex: 1,
          itemStyle: { color: '#4b5563' },
          markLine,
        },
        {
          name: '份额净申赎(亿份)',
          type: 'bar',
          data: flowData,
          xAxisIndex: 2,
          yAxisIndex: 2,
          markLine,
        },
        {
          name: '综合概率',
          type: 'line',
          data: probData,
          xAxisIndex: 3,
          yAxisIndex: 3,
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 1.5 },
          areaStyle: { opacity: 0.08 },
          markLine: probMarkLine,
        },
      ],
      dataZoom: [
        insideZoom,
        {
          type: 'slider',
          xAxisIndex: [0, 1, 2, 3],
          top: '92%',
          height: 16,
          borderColor: '#374151',
          backgroundColor: '#111827',
          fillerColor: 'rgba(75, 118, 99, 0.3)',
          handleStyle: { color: '#6b7280' },
          textStyle: { color: '#6b7280' },
        },
      ],
    },
    dates,
  }
}
