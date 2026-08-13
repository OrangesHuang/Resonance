import { useCallback, useRef } from 'react'
import type { ECharts } from 'echarts'

interface Registered {
  inst: ECharts
  getDates: () => string[]
}

type Listener = (date: string | null) => void

/** 五图鼠标白线(axisPointer)联动 — 按"日期值"对齐。
 *
 * echarts.connect 按索引同步 tooltip: dates 相同的图联动正确, 不同长度的
 * 图(ETF 334 天 vs 市场情绪 471 天)会错位。此 hook 用日期字符串广播:
 * 任一图 hover → 其他图 dispatchAction showTip 定位到该日(单值 convertToPixel)。
 * 另提供 subscribe 供无法渲染 axisPointer 的图(heatmap)自行画竖线。
 * zoom: 缩放百分比即时广播(同事件循环内 dispatchAction, 原生手感,
 * 无 React/防抖链路延迟; zooming 标志防环)。
 */
export function useAxisPointerBridge() {
  const charts = useRef<Registered[]>([])
  const listeners = useRef<Set<Listener>>(new Set())
  const zooming = useRef(false)
  const lastZoom = useRef<[number, number, number] | null>(null)

  /** getDates 为 getter: 切换标的/数据更新后取最新日期序列 */
  const register = useCallback((inst: ECharts, getDates: () => string[]) => {
    if (!charts.current.some(c => c.inst === inst)) {
      charts.current.push({ inst, getDates })
    }
  }, [])

  const unregister = useCallback((inst: ECharts) => {
    charts.current = charts.current.filter(c => c.inst !== inst)
  }, [])

  /** 订阅 hover 日期变化(热力图等无法画 axisPointer 的图用) */
  const subscribe = useCallback((cb: Listener) => {
    listeners.current.add(cb)
    return () => {
      listeners.current.delete(cb)
    }
  }, [])

  /** 缩放百分比即时广播: 除来源图外所有图同步 dataZoom(防环标志)。 */
  const zoom = useCallback((start: number, end: number, source: ECharts | null) => {
    if (zooming.current) return
    // 去重: 相同缩放值短时间内重复广播直接忽略(防异步链循环)
    const now = Date.now()
    if (lastZoom.current) {
      const [ls, le, lt] = lastZoom.current
      if (Math.abs(ls - start) < 0.001 && Math.abs(le - end) < 0.001 && now - lt < 200) {
        return
      }
    }
    lastZoom.current = [start, end, now]
    zooming.current = true
    try {
      for (const { inst } of charts.current) {
        if (inst === source) continue
        try {
          inst.dispatchAction({ type: 'dataZoom', start, end })
        } catch {
          // 忽略
        }
      }
    } finally {
      zooming.current = false
    }
  }, [])

  /** 广播 hover 日期: 所有已注册图显示白线 + 通知订阅者 */
  const show = useCallback((date: string | null) => {
    // 清理已 dispose 的实例(dispose 后 getZr 抛错)
    charts.current = charts.current.filter(c => {
      try {
        c.inst.getZr()
        return true
      } catch {
        return false
      }
    })
    for (const { inst, getDates } of charts.current) {
      try {
        if (!date) {
          inst.dispatchAction({ type: 'hideTip' })
          continue
        }
        const dates = getDates()
        const idx = dates.indexOf(date)
        if (idx < 0) continue
        const px = (inst.convertToPixel({ xAxisIndex: 0 }, idx) as number) ?? 0
        if (Number.isNaN(px)) continue
        // y 取图表垂直中心: 固定值可能落在 grid 外导致 showTip 无效
        inst.dispatchAction({ type: 'showTip', x: px, y: (inst.getHeight?.() ?? 100) / 2 })
      } catch {
        // 忽略实例未就绪/坐标转换异常
      }
    }
    for (const cb of listeners.current) {
      try {
        cb(date)
      } catch {
        // 忽略订阅者异常
      }
    }
  }, [])

  return { register, unregister, subscribe, show, zoom }
}

export type AxisPointerBridge = ReturnType<typeof useAxisPointerBridge>
