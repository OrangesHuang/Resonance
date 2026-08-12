import { useCallback } from 'react'
import { useLocalStorage } from './useLocalStorage'

export const DEFAULT_PINNED = ['159352', '589680', '515080']

const STORAGE_KEY = 'pinnedEtfs'
const LEGACY_KEY = 'etf_favorites'

function migrateLegacy(): void {
  try {
    const legacy = localStorage.getItem(LEGACY_KEY)
    if (!legacy) return
    const legacyList = JSON.parse(legacy) as string[]
    if (!Array.isArray(legacyList)) return
    const raw = localStorage.getItem(STORAGE_KEY)
    const current = raw ? (JSON.parse(raw) as string[]) : []
    const merged = Array.from(new Set([...current, ...legacyList]))
    localStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
    localStorage.removeItem(LEGACY_KEY)
  } catch {
    // localStorage 不可用或数据损坏时忽略
  }
}

/** 全站统一的 ETF 收藏源（共振置顶 / 走势对比勾选 / 流向分析星标共用）。 */
export function usePinnedEtfs() {
  migrateLegacy()
  const [pinned, setPinned] = useLocalStorage<string[]>(STORAGE_KEY, DEFAULT_PINNED)
  const togglePin = useCallback((code: string) => {
    setPinned(prev => prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code])
  }, [setPinned])
  return { pinned, togglePin }
}
