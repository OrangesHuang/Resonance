import { useCallback, useState } from 'react'

const STORAGE_KEY = 'etf_favorites'

function loadFavorites(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<string[]>(loadFavorites)

  const toggleFavorite = useCallback((code: string) => {
    setFavorites(prev => {
      const next = prev.includes(code)
        ? prev.filter(c => c !== code)
        : [...prev, code]
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        // localStorage 不可用时仅内存态
      }
      return next
    })
  }, [])

  return { favorites, toggleFavorite }
}
