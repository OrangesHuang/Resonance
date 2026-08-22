import { useCallback, useMemo, useRef } from 'react'
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
  const showing = useRef(false)

  /** getDates 为 getter: 切换标的/数据更新后取最新日期序列。
   *  已 dispose 的实例(StrictMode 双挂载/echarts-for-react 临时实例
   *  竞态残留)直接拒绝, 避免广播打到死实例上。 */
  const register = useCallback((inst: ECharts, getDates: () => string[]) => {
    // isDisposed 探活: dispose 后 getZr 仍返回 null 不抛错, 会漏进广播名单
    if (inst.isDisposed?.()) return
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

  /** 是否正处于 zoom 广播栈内: 其他图广播来的 dataZoom 事件在此栈内
   *  同步触发, 订阅方可据此区分「外部驱动」与「用户直接操作」——外部
   *  驱动的事件不得回写缩放状态(dateWindow), 否则形成跨图反馈风暴。 */
  const isZooming = useCallback(() => zooming.current, [])

  /** 缩放百分比即时广播: 除来源图外所有图同步 dataZoom(防环标志)。 */
  const zoom = useCallback((start: number, end: number, source: ECharts | null) => {
    if (zooming.current) return
    // 清理已 dispose 的实例: isDisposed 为真直接移除(dispose 后 dispatchAction
    // 会打 "has been disposed" 警告并可能影响新实例联动, 必须清干净)
    charts.current = charts.current.filter(c => !c.inst.isDisposed?.())
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

  /** 广播 hover 日期: 除来源图外所有图显示白线 + 通知订阅者。
   *  跳过来源图: 来源图由原生 axisPointer 定位 tooltip, 广播回来的
   *  showTip(图表中心 y)会与鼠标位置交替覆盖导致 tooltip 飘移。
   *  再入抑制: showTip 同步触发各图 updateAxisPointer, 其 handler 又以自己
   *  为来源再次广播回来(间接回环), 把 K线 tooltip 拉回图表中心再被鼠标
   *  位置覆盖; 广播期间再入的 show 直接忽略, 只保留第一跳(来源图→其他图)。 */
  const show = useCallback((date: string | null, source: ECharts | null = null) => {
    if (showing.current) return
    showing.current = true
    try {
      // 清理已 dispose 的实例(dispose 后 dispatchAction 打警告, 直接按标记移除)
      charts.current = charts.current.filter(c => !c.inst.isDisposed?.())
      for (const { inst, getDates } of charts.current) {
        if (inst === source) continue
        try {
          if (!date) {
            // hideTip 只隐藏 tooltip; 全局 axisPointer 需显式 leave 才隐藏
            // (此前由 echarts.connect 组传播 leave 触发, 现统一由 bridge 处理)
            inst.dispatchAction({ type: 'hideTip' })
            inst.dispatchAction({ type: 'updateAxisPointer', currTrigger: 'leave' })
            continue
          }
          const dates = getDates()
          const idx = dates.indexOf(date)
          if (idx < 0) continue
          const px = (inst.convertToPixel({ xAxisIndex: 0 }, idx) as number) ?? 0
          if (Number.isNaN(px)) continue
          // y 取图表高度 20%: 高度中点在多 grid 图(如 K线 4 格)上落在
          // 网格间隙, containPoint=false 导致 showTip 无效; 首格通常从
          // ~10% 高度开始, 20% 保证落在所有图的第一个网格内
          inst.dispatchAction({ type: 'showTip', x: px, y: (inst.getHeight?.() ?? 100) * 0.2 })
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
    } finally {
      showing.current = false
    }
  }, [])

  // 引用稳定: 子组件 useEffect([bridge]) 卸载清理依赖此引用;
  // 若每次渲染返回新对象, cleanup 会被反复触发把实例移出桥(联动失效)
  return useMemo(() => ({ register, unregister, subscribe, show, zoom, isZooming }), [register, unregister, subscribe, show, zoom, isZooming])
}

export type AxisPointerBridge = ReturnType<typeof useAxisPointerBridge>