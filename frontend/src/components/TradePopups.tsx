import type { PortfolioTrade } from '../api/types'

export type TradeRow = {
  date: string
  kind: string
  kind_label: string
  name: string
  code: string
  signal_date: string
  units: number
  price: number
  amount: number
}

// 转仓 = 卖旧买新: 把 SWITCH(转出) 与其对应 BUY(转入) 合并为单行,
// 如 "中证红利(减半) → 科创综指"; 无关联的 BUY 照常显示
export function buildRows(trades: PortfolioTrade[]): TradeRow[] {
  const byTo = new Map<string, PortfolioTrade[]>()
  for (const s of trades) {
    if (s.kind !== 'SWITCH') continue
    const arr = byTo.get(s.to_code ?? '') ?? []
    arr.push(s)
    byTo.set(s.to_code ?? '', arr)
  }
  const consumed = new Set<PortfolioTrade>()
  const rows: TradeRow[] = []
  for (const t of trades) {
    // SWITCH 先于其 BUY 入日志, 第一遍跳过, 避免被当作孤立转仓提前输出
    if (consumed.has(t) || t.kind === 'SWITCH') continue
    const group = t.kind === 'BUY' ? byTo.get(t.code) : undefined
    if (group && group.length > 0) {
      for (const s of group) consumed.add(s)
      const tag = (s: PortfolioTrade) =>
        s.action === 'LIQUIDATE' ? '(清仓)' : s.action === 'REDUCE' ? '(减半)' : ''
      rows.push({
        date: t.date,
        kind: 'SWITCH',
        kind_label: '转仓',
        name: `${group.map(s => `${s.name}${tag(s)}`).join(' + ')} → ${t.name}`,
        code: t.code,
        signal_date: t.signal_date,
        units: t.units,
        price: t.price,
        amount: t.amount,
      })
      continue
    }
    rows.push({
      date: t.date,
      kind: t.kind,
      kind_label: t.kind_label,
      name: t.name,
      code: t.code,
      signal_date: t.signal_date,
      units: t.units,
      price: t.price,
      amount: t.amount,
    })
  }
  // 未被消费的 SWITCH(仅 SKIP 极端场景: 转出后仍不足半份, 当日无对应 BUY)防御显示
  for (const t of trades) {
    if (t.kind !== 'SWITCH' || consumed.has(t)) continue
    rows.push({
      date: t.date,
      kind: 'SWITCH',
      kind_label: t.kind_label,
      name: t.to_name ? `${t.name} → ${t.to_name}` : t.name,
      code: t.code,
      signal_date: t.signal_date,
      units: t.units,
      price: t.price,
      amount: t.amount,
    })
  }
  return rows
}

const KIND_STYLE: Record<string, string> = {
  BUY: 'text-green-400',
  TOPUP: 'text-sky-400',
  SWITCH: 'text-amber-400',
  SELL: 'text-red-400',
  SKIP: 'text-gray-500',
}

export interface PopupState {
  key: string
  date: string
  items: TradeRow[]
  left: number
  top: number
}

const POPUP_W = 220
const POPUP_H_BASE = 56          // 内边距+标题行(略偏大, 防重叠判定保守)
const POPUP_H_PER_ROW = 22

export function popupHeight(items: TradeRow[]): number {
  return POPUP_H_BASE + items.length * POPUP_H_PER_ROW
}

function intersects(a: { left: number; top: number; w: number; h: number },
                    b: { left: number; top: number; w: number; h: number }): boolean {
  return a.left < b.left + b.w && a.left + a.w > b.left &&
         a.top < b.top + b.h && a.top + a.h > b.top
}

/** 在圆点上方放弹窗: x 居中于圆点, y 从圆点上方逐级上移, 上方放不下再试下方;
 *  全被占用时按 x 偏移(±160/±320)错开再试, 保证与已打开弹窗矩形不重叠。 */
export function placePopup(x: number, y: number, items: TradeRow[],
                           existing: PopupState[],
                           containerW: number, containerH: number): { left: number; top: number } {
  const w = POPUP_W
  const h = popupHeight(items)
  const occupied = existing.map(p => ({
    left: p.left, top: p.top, w: POPUP_W, h: popupHeight(p.items),
  }))
  const yCands: number[] = []
  for (let t = y - h - 14; t >= 4; t -= h + 6) yCands.push(t)
  for (let t = y + 14; t + h <= containerH - 4; t += h + 6) yCands.push(t)
  yCands.push(Math.max(4, Math.min(y - h - 14, containerH - h - 4)))
  for (const ox of [0, -160, 160, -320, 320]) {
    const left = Math.max(8, Math.min(x - w / 2 + ox, containerW - w - 8))
    for (const top of yCands) {
      if (!occupied.some(o => intersects({ left, top, w, h }, o))) {
        return { left, top }
      }
    }
  }
  return { left: Math.max(8, Math.min(x - w / 2, containerW - w - 8)),
           top: yCands[yCands.length - 1] }
}

export function TradePopup({ popup, onClose }: { popup: PopupState; onClose: () => void }) {
  return (
    <div
      className="absolute bg-gray-800 border border-gray-600 rounded-lg p-3 shadow-lg z-10"
      style={{ left: popup.left, top: popup.top, width: POPUP_W }}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold text-white">{popup.date}</span>
        <button onClick={onClose}
          className="text-gray-400 hover:text-white text-lg leading-none px-1">&times;</button>
      </div>
      {popup.items.map((t, i) => (
        <div key={i} className="text-xs mb-1.5 last:mb-0">
          <span className={`font-bold ${KIND_STYLE[t.kind] ?? 'text-gray-300'}`}>{t.kind_label}</span>
          <span className="text-gray-300 ml-1">{t.name}</span>
          <span className="text-gray-500 ml-1">{t.price} × {(t.amount / 10000).toFixed(2)}万</span>
        </div>
      ))}
    </div>
  )
}
