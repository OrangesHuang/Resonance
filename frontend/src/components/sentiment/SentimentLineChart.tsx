import { useEffect, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsType } from 'echarts'
import { windowToZoom, type DateWindow } from '../common/chartZoom'

interface LineSpec {
  name: string
  data: Array<number | null>
  color: string
  width?: number
}

interface BarSpec {
  name: string
  data: Array<number | null>
  colorFor?: (v: number) => string
}

interface Props {
  dates: string[]
  lines: LineSpec[]
  bars?: BarSpec
  height?: number | string
  yFormatter?: (v: number) => string
  barFormatter?: (v: number) => string
  lineTip?: (v: number) => string
  barTip?: (v: number) => string
  onReady?: (instance: EChartsType) => void
  selectedDate?: string | null
  onSelectDate?: (date: string) => void
  /** 仅跟随: K线为缩放主控, dateWindow 变化时重建当前缩放窗口 */
  dateWindow?: DateWindow | null
  /** 五图白线联动: 注册实例 + hover 上报 + 接收广播 */
  bridge?: {
    register: (inst: EChartsType, getDates: () => string[]) => void
    unregister: (inst: EChartsType) => void
    show: (date: string | null, source?: EChartsType | null) => void
    zoom: (start: number, end: number, source: EChartsType | null) => void
  }
}

interface ClickParam {
  dataIndex?: number
}

interface DataZoomEvent {
  start?: number
  end?: number
  batch?: Array<{ start: number; end: number }>
}

interface TooltipParam {
  axisValue: string
  marker: string
  seriesName: string
  seriesType: string
  value: number | { value: number } | null
}

const AXIS_LABEL = '#6b7280'
const SPLIT_LINE = '#1f2937'

export default function SentimentLineChart({ dates, lines, bars, height = 320, yFormatter, barFormatter, lineTip, barTip, onReady, selectedDate, onSelectDate, dateWindow, bridge }: Props) {
  const chartRef = useRef<EChartsType | null>(null)
  const datesRef = useRef(dates)
  datesRef.current = dates
  const onSelectDateRef = useRef(onSelectDate)
  onSelectDateRef.current = onSelectDate
  // 本图缩放状态(用户拖滑块 或 K线广播)持久化: option 以 notMerge 重建时
  // 若回退到 windowToZoom(dateWindow) 会把手动缩放重置为全量,
  // 必须用 zoomRef 保持最近一次缩放(2026-08 修复「点击后缩放到最大」)。
  const zoomRef = useRef<{ start: number; end: number } | null>(null)
  const boundZrRef = useRef<unknown>(null)

  // 点击定位走 zr 层: 任意位置(不必命中折线)像素→日期索引→选中该日,
  // 与 K线/红绿灯一致。绑在 onChartReady(echarts-for-react 首渲染 ref 是
  // 临时实例, mount effect 绑定会失效); boundZrRef 防 StrictMode 重复绑。
  const onChartReady = (inst: EChartsType) => {
    chartRef.current = inst
    onReady?.(inst)
    if (!inst.isDisposed?.()) bridge?.register(inst, () => datesRef.current)
    const zr = inst.getZr()
    if (!zr || boundZrRef.current === zr) return
    boundZrRef.current = zr
    zr.on('click', (e: { offsetX?: number }) => {
      try {
        if (e.offsetX == null) return
        const px = inst.convertFromPixel({ xAxisIndex: 0 }, e.offsetX) as number | null
        const idx = px != null && !Number.isNaN(px) ? Math.round(px) : -1
        if (idx < 0 || idx >= datesRef.current.length) return
        const d = datesRef.current[idx]
        if (!d || !onSelectDateRef.current) return
        onSelectDateRef.current(d)
      } catch {
        // 忽略坐标转换异常
      }
    })
  }

  // 外部 hover 日期广播 → 白线跟随(按日期值定位, 与自身 dates 无关)
  useEffect(() => {
    const inst = chartRef.current
    if (!inst || inst.isDisposed?.()) return
    inst.dispatchAction({ type: 'hideTip' })
  }, [selectedDate])

  // 卸载清理: 从桥中移除已 dispose 实例
  useEffect(() => {
    return () => {
      if (chartRef.current) bridge?.unregister(chartRef.current)
    }
  }, [bridge])

  if (dates.length === 0) {
    return <div className="text-gray-500 text-center py-10">暂无数据</div>
  }

  const hasBars = !!bars
  const hasLines = lines.length > 0
  const splitGrid = hasBars && hasLines
  const fmt = yFormatter ?? ((v: number) => `${v}`)
  const barFmt = barFormatter ?? ((v: number) => `${v.toFixed(0)}`)
  const tipFmt = lineTip ?? fmt

  const grids = splitGrid
    ? [
        { left: 60, right: 20, top: 20, height: '58%' },
        { left: 60, right: 20, top: '74%', height: '16%' },
      ]
    : [{ left: 60, right: 20, top: 20, bottom: 60 }]

  const barAxis = splitGrid ? 1 : 0

  const xAxes: Array<Record<string, unknown>> = [
    { type: 'category', data: dates, gridIndex: 0, boundaryGap: !hasLines, axisLabel: { color: AXIS_LABEL, fontSize: 10 } },
  ]
  const yAxes: Array<Record<string, unknown>> = [
    {
      type: 'value',
      gridIndex: 0,
      scale: true,
      splitLine: { lineStyle: { color: SPLIT_LINE } },
      axisLabel: { color: AXIS_LABEL, formatter: (v: number) => (hasLines ? fmt(v) : barFmt(v)) },
    },
  ]

  if (splitGrid) {
    xAxes.push({ type: 'category', data: dates, gridIndex: 1, boundaryGap: true, axisLabel: { show: false } })
    yAxes.push({
      type: 'value',
      gridIndex: 1,
      scale: true,
      splitNumber: 2,
      splitLine: { show: false },
      axisLabel: { color: AXIS_LABEL, fontSize: 9, formatter: (v: number) => barFmt(v) },
    })
  }

  const series: Array<Record<string, unknown>> = lines.map(l => ({
    name: l.name,
    type: 'line',
    data: l.data,
    xAxisIndex: 0,
    yAxisIndex: 0,
    showSymbol: false,
    smooth: false,
    connectNulls: false,
    lineStyle: { width: l.width ?? 1.5, color: l.color },
    itemStyle: { color: l.color },
  }))

  if (hasBars && bars) {
    const barData = bars.data.map(v => {
      if (v == null) return null
      const color = bars.colorFor ? bars.colorFor(v) : '#4b5563'
      return { value: v, itemStyle: { color } }
    })
    series.push({
      name: bars.name,
      type: 'bar',
      data: barData,
      xAxisIndex: barAxis,
      yAxisIndex: barAxis,
      barMaxWidth: splitGrid ? 6 : 10,
    })
  }

  // 初始(无缩放历史)跟随 K线 dateWindow; 一旦本图发生过缩放(K线广播
  // 或用户拖动), 以 zoomRef 为准 — 否则点击选中日期触发 notMerge 重建
  // 会把缩放重置回 windowToZoom(dateWindow)(dateWindow 为 null 即全量)。
  const zoom = zoomRef.current ?? windowToZoom(dates, dateWindow ?? null)

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      transitionDuration: 0,
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: (params: TooltipParam[]) => {
        const date = params[0]?.axisValue ?? ''
        const rows = params.map(p => {
          const raw = p.value
          const num = raw && typeof raw === 'object' ? raw.value : raw
          if (num == null || typeof num !== 'number') return `${p.marker}${p.seriesName}: -`
          const text = p.seriesType === 'bar'
            ? (barTip ? barTip(num) : `${num.toFixed(2)} 亿`)
            : tipFmt(num)
          return `${p.marker}${p.seriesName}: ${text}`
        })
        return `${date}<br/>${rows.join('<br/>')}`
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    legend: {
      data: lines.map(l => l.name),
      textStyle: { color: AXIS_LABEL, fontSize: 10 },
      top: 0,
      right: 20,
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    series,
    dataZoom: [
      { type: 'inside', xAxisIndex: splitGrid ? [0, 1] : [0], start: zoom.start, end: zoom.end },
      {
        type: 'slider',
        xAxisIndex: splitGrid ? [0, 1] : [0],
        start: zoom.start,
        end: zoom.end,
        bottom: 8,
        height: 18,
        borderColor: '#374151',
        backgroundColor: '#111827',
        fillerColor: 'rgba(75, 85, 99, 0.3)',
        handleStyle: { color: '#6b7280' },
        textStyle: { color: '#6b7280' },
      },
    ],
  }

  const onEvents: Record<string, (params: ClickParam & DataZoomEvent & { x?: number }) => void> | undefined =
    onSelectDate || bridge
      ? {
          // 点击定位由 zr 层处理(onChartReady 绑定): 任意位置即可,
          // ECharts series click 需命中折线才给 dataIndex, 体验割裂
          updateAxisPointer: params => {
            // 情绪图在 SENTIMENT_SYNC_GROUP connect 组内: 这里再广播会与
            // connect 的组内传播形成回路(卡死), 且事件不带像素 x 本就无法
            // 按日期对齐 — 保持不广播(白线联动由 K线/红绿灯/热力图方向提供)
            if (!bridge || params.x == null) return
            try {
              const px = chartRef.current?.convertFromPixel({ xAxisIndex: 0 }, params.x) as number | null
              const idx = px != null && !Number.isNaN(px) ? Math.round(px) : -1
              if (idx >= 0 && idx < dates.length) bridge.show(dates[idx], chartRef.current)
            } catch {
              // 忽略
            }
          },
          datazoom: e => {
            const z = e.batch ? e.batch[0] : e
            if (z.start == null || z.end == null) return
            // 持久化最近一次缩放(用户拖动 或 K线广播): notMerge 重建时
            // 保持当前窗口, 避免点击选中日期把缩放重置回全量
            zoomRef.current = { start: z.start, end: z.end }
            // 缩放百分比广播到所有图(K线/红绿灯/热力图跟随), 双向联动。
            // 反馈环已切断: K线对外部驱动(广播栈内触发)的 datazoom 不回写
            // dateWindow(见 ResonanceKline), 故本图缩放不会引发
            // 「K线回写 → 本图 notMerge 重建 → 再广播」的假死风暴。
            // 本图不回写 dateWindow(缩放状态归 K线维护)。
            bridge?.zoom(z.start, z.end, chartRef.current)
          },
          globalout: () => {
            // 移出图表 → 清除全图白线(与 K线一致, 防止残留)
            bridge?.show(null)
          },
        }
      : undefined

  return (
    <ReactECharts
      option={{
        ...option,
        series: option.series.map((s, i) => ({
          ...s,
          ...(onSelectDate ? { cursor: 'pointer' } : {}),
          ...(selectedDate && dates.includes(selectedDate)
            ? {
                markLine: {
                  symbol: 'none',
                  silent: true,
                  animation: false,
                  // 索引定位: 与K线/红绿灯/热力图竖线严格对齐(类别中心)
                  data: [{ xAxis: dates.indexOf(selectedDate) }],
                  lineStyle: { color: '#38bdf8', type: 'dashed', width: 1 },
                  label: { show: i === 0, position: 'start', color: '#38bdf8', fontSize: 9 },
                },
              }
            : {}),
        })),
      }}
      onEvents={onEvents}
      style={{ height }}
      notMerge
      lazyUpdate
      onChartReady={onChartReady}
    />
  )
}
