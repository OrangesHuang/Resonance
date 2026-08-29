import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchResonance, fetchResonanceDay, fetchEtfHistory } from '../api/client'
import { cacheGet, cacheSet, cacheValid, mergeByDate, settledData } from '../utils/idbCache'
import { CACHE_SCHEMA, type ResonanceOverview, type ResonanceHistoryPoint, type EtfHistoryResponse, type KlinePoint, type DailySignal } from '../api/types'

// 缓存优先: 历史数据(≥5交易日)存 IndexedDB, 增量只拉最近 N 个交易日
async function fetchResonanceCached(code: string): Promise<ResonanceOverview> {
  const key = `resonance:${code}`
  const cached = await cacheGet<ResonanceHistoryPoint>(key)
  const valid = cacheValid(cached)
  const resp = await fetchResonance(code, valid ? cached.endDate : undefined)
  const merged = mergeByDate(valid ? cached.data : [], resp.history)
  const endDate = resp.safe_end ?? (valid ? cached.endDate : '')
  await cacheSet(key, {
    data: settledData(merged, endDate),
    endDate,
    cachedAt: Date.now(),
    schema: CACHE_SCHEMA,
  })
  return { ...resp, history: merged }
}

export function useResonance(code = '510300') {
  return useQuery({
    queryKey: ['resonance', code],
    queryFn: () => fetchResonanceCached(code),
    placeholderData: keepPreviousData,
    refetchInterval: false,
    refetchIntervalInBackground: false,
  })
}

export function useResonanceDay(code: string, date: string | null) {
  return useQuery({
    queryKey: ['resonance', code, 'day', date],
    queryFn: () => fetchResonanceDay(code, date as string),
    enabled: !!date,
    placeholderData: keepPreviousData,
    refetchInterval: false,
    refetchIntervalInBackground: false,
  })
}

// K线 + daily_signals 缓存优先(两个 key 共享同一 endDate)
async function fetchEtfHistoryCached(code: string, days: number): Promise<EtfHistoryResponse> {
  const kcached = await cacheGet<KlinePoint>(`kline:${code}`)
  const scached = await cacheGet<DailySignal>(`kline-signals:${code}`)
  const valid = cacheValid(kcached)
  const since = valid ? kcached.endDate : undefined
  const resp = await fetchEtfHistory(code, days, since)
  const kMerged = mergeByDate(valid ? kcached.data : [], resp.kline)
  const sMerged = mergeByDate(valid && scached ? scached.data : [], resp.daily_signals)
  const endDate = resp.safe_end ?? (valid ? kcached.endDate : '')
  const now = Date.now()
  await Promise.all([
    cacheSet(`kline:${code}`, { data: settledData(kMerged, endDate), endDate, cachedAt: now, schema: CACHE_SCHEMA }),
    cacheSet(`kline-signals:${code}`, { data: settledData(sMerged, endDate), endDate, cachedAt: now, schema: CACHE_SCHEMA }),
  ])
  return { ...resp, kline: kMerged, daily_signals: sMerged }
}

export function useEtfHistory(code: string, days = 3200) {
  return useQuery({
    queryKey: ['etfHistory', code],
    queryFn: () => fetchEtfHistoryCached(code, days),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60 * 1000,
  })
}
