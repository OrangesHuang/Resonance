import { useEffect, useMemo, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import type { ECharts } from 'echarts'
import type { ResonanceHistoryPoint } from '../../api/types'
import type { AxisPointerBridge } from '../../hooks/useAxisPointerBridge'

const AXIS_LABEL = '#6b7280'
const SPLIT_LINE = '#1f2937'

interface TooltipParam {
  axisValue: string
  marker: string
  seriesName: string
  value: number | { value: number } | null
}

interface ClickParam {
  dataIndex?: number
}

export default function ResonanceChart({ history, selectedDate, onSelectDate, bridge }: {
  history: ResonanceHistoryPoint[]
  selectedDate?: string | null
  onSelectDate?: (date: string) => void
  bridge?: AxisPointerBridge
}) {
  const instRef = useRef<ECharts | null>(null)
  const boundZrRef = useRef<unknown>(null)
  // 卸载清理: 从桥中移除已 dispose 实例(切换 ETF 重挂载, 防死实例广播)
  useEffect(() => {
    return () => {
      if (instRef.current) bridge?.unregister(instRef.current)
    }
  }, [bridge])

  const dates = useMemo(() => history.map(h => h.date), [history])
  const datesRef = useRef(dates)
  datesRef.current = dates

  const onChartReady = (inst: ECharts) => {
    instRef.current = inst
    if (inst.isDisposed?.()) return
    bridge?.register(inst, () => datesRef.current)
    // zr 层点击: 任意位置(白线所在列)点击都选中该日, 无需点中柱子
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
        if (d) onSelectDate?.(d)
      } catch {
        // 忽略
      }
    })
  }

  // option 用 useMemo 缓存: dateWindow 变化不重建 option(避免缩放期间
  // 高频 setOption 触发 "setOption during main process" 报错)
  const option = useMemo(() => {
    const redData = history.map(h => h.red)
    const greenData = history.map(h => -h.green)
    // notMerge 重建会重置 dataZoom: 从实例实时读当前缩放回填
    // 实例可能刚被 dispose(key 重挂载间隙): getOption 抛错则回退全量
    let zStart = 0
    let zEnd = 100
    try {
      const dz = instRef.current?.getOption().dataZoom as
        | Array<{ start?: number; end?: number }>
        | undefined
      zStart = dz?.[0]?.start ?? 0
      zEnd = dz?.[0]?.end ?? 100
    } catch {
      // 实例已 dispose: 用默认全量缩放
    }
    return {
      backgroundColor: 'transparent',
      animation: false,
      tooltip: {
        transitionDuration: 0,
        trigger: 'axis',
        backgroundColor: '#111827',
        borderColor: '#374151',
        textStyle: { color: '#e5e7eb' },
        axisPointer: {
          type: 'line',
          lineStyle: { color: '#9ca3af', type: 'dashed', width: 1 },
        },
        formatter: (params: TooltipParam[]) => {
          const date = params[0]?.axisValue ?? ''
          const idx = dates.indexOf(date)
          if (idx < 0) return date
          const p = history[idx]
          return `${date}<br/>红灯 ${p.red} 盏<br/>绿灯 ${p.green} 盏`
        },
      },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      legend: {
        data: ['红灯数', '绿灯数'],
        textStyle: { color: AXIS_LABEL, fontSize: 10 },
        top: 0,
        right: 20,
      },
      grid: { left: 40, right: 20, top: 30, bottom: 60 },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: true,
        axisLabel: { color: AXIS_LABEL, fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        min: -5,
        max: 5,
        interval: 1,
        splitLine: { lineStyle: { color: SPLIT_LINE } },
        axisLabel: { color: AXIS_LABEL, formatter: (v: number) => `${Math.abs(v)}` },
      },
      series: [
        {
          name: '红灯数',
          type: 'bar',
          data: redData,
          stack: 'resonance',
          barMaxWidth: 10,
          itemStyle: { color: '#ef4444' },
          cursor: 'pointer',
          ...(selectedDate && dates.includes(selectedDate)
            ? {
                markLine: {
                  symbol: 'none',
                  silent: true,
                  animation: false,
                  data: [{ xAxis: dates.indexOf(selectedDate) }],
                  lineStyle: { color: '#38bdf8', type: 'dashed', width: 1 },
                  label: { show: false },
                },
              }
            : {}),
        },
        {
          name: '绿灯数',
          type: 'bar',
          data: greenData,
          stack: 'resonance',
          barMaxWidth: 10,
          itemStyle: { color: '#22c55e' },
          cursor: 'pointer',
        },
      ],
      dataZoom: [
        { type: 'inside', start: zStart, end: zEnd },
        {
          type: 'slider',
          start: zStart,
          end: zEnd,
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
  }, [history, dates, selectedDate])

  // 缩放同步: 靠 connect 组(同 dates 图)+ K线 bridge.zoom 广播;
  // 不再自行 dispatch dateWindow(避免窗口横跳循环)

  const onEvents = {
    click: (params: ClickParam) => {
      if (params.dataIndex == null) return
      const d = dates[params.dataIndex]
      if (d) onSelectDate?.(d)
    },
    updateAxisPointer: (e: { x?: number; axesInfo?: Array<{ axisDim?: string; value?: unknown }> }) => {
      if (!bridge) return
      try {
        // 事件不带像素 x: 用 axesInfo 的 x 轴索引取日期(与 K线日期序列对齐)
        const axisVal = e.axesInfo?.find(a => a.axisDim === 'x')?.value
        if (typeof axisVal === 'number' && axisVal >= 0 && axisVal < dates.length) {
          bridge.show(dates[axisVal], instRef.current)
          return
        }
        if (e.x == null) return
        const px = instRef.current?.convertFromPixel({ xAxisIndex: 0 }, e.x) as number | null
        const idx = px != null && !Number.isNaN(px) ? Math.round(px) : -1
        if (idx >= 0 && idx < dates.length) bridge.show(dates[idx], instRef.current)
      } catch {
        // 忽略
      }
    },
    datazoom: (e: { start?: number; end?: number; batch?: Array<{ start?: number; end?: number }> }) => {
      const z = e.batch ? e.batch[0] : e
      if (z.start == null || z.end == null) return
      // 缩放即时广播到所有图(按百分比, 与 K线/情绪图一致)
      bridge?.zoom(z.start, z.end, instRef.current)
    },
    globalout: () => {
      // 移出图表 → 清除全图白线(与 K线一致, 防止热力图粗线残留)
      bridge?.show(null)
    },
  }

  if (history.length === 0) {
    return <div className="text-gray-500 text-center py-10">暂无数据</div>
  }

  return (
    <ReactECharts
      onChartReady={onChartReady}
      option={option}
      onEvents={onEvents}
      style={{ height: 260 }}
      notMerge
    />
  )
}