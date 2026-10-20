// Shared display formatters for prices and signed percentages.

export function fmtPrice(v: number | null | undefined, digits = 3): string {
  return v == null || !Number.isFinite(v) ? '-' : v.toFixed(digits)
}

// A-share color convention: up is red, down is green.
export const UP_COLOR = '#ef4444'
export const DOWN_COLOR = '#22c55e'

export function pctColor(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v) || v === 0) return '#9ca3af'
  return v > 0 ? UP_COLOR : DOWN_COLOR
}

export function fmtSignedPct(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return '-'
  return `${v >= 0 ? '+' : ''}${v.toFixed(digits)}%`
}

// ECharts calls the value-axis formatter with (value, index); wrapping keeps
// the index out of the digits argument of fmtPrice.
export function priceAxisLabel(color: string) {
  return { color, formatter: (v: number) => fmtPrice(v) }
}

// The crosshair tag on a value axis is rounded by ECharts to a precision derived
// from the axis extent, so it drops to 2dp on wide ranges. Pin it to the same
// 3dp rule as the axis labels.
export const pricePointerLabel = {
  label: { formatter: (p: { value: number | string | Date }) => fmtPrice(Number(p.value)) },
}
