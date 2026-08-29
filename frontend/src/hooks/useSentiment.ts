import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchMarketSentiment, refreshSentiment } from '../api/client'
import { cacheGet, cacheSet, cacheValid, mergeByDate, settledData } from '../utils/idbCache'
import { CACHE_SCHEMA, type SentimentOverview, type TurnoverPoint, type MarginPoint } from '../api/types'

// 缓存优先: 成交额/融资历史存 IndexedDB, 增量只拉最近 N 个交易日
// (summary/zone 为当前状态, 后端全量计算, 不受 since 影响)
async function fetchSentimentCached(): Promise<SentimentOverview> {
  const tc = await cacheGet<TurnoverPoint>('sentiment-turnover')
  const mc = await cacheGet<MarginPoint>('sentiment-margin')
  const valid = cacheValid(tc) && cacheValid(mc)
  const since = valid ? (tc as { endDate: string }).endDate : undefined
  const resp = await fetchMarketSentiment(since)
  const tMerged = mergeByDate(valid ? tc.data : [], resp.turnover)
  const mMerged = mergeByDate(valid ? mc.data : [], resp.margin)
  const endDate = resp.safe_end ?? (valid ? tc.endDate : '')
  const now = Date.now()
  await Promise.all([
    cacheSet('sentiment-turnover', { data: settledData(tMerged, endDate), endDate, cachedAt: now, schema: CACHE_SCHEMA }),
    cacheSet('sentiment-margin', { data: settledData(mMerged, endDate), endDate, cachedAt: now, schema: CACHE_SCHEMA }),
  ])
  return { ...resp, turnover: tMerged, margin: mMerged }
}

export function useSentiment() {
  return useQuery({
    queryKey: ['sentiment', 'overview'],
    queryFn: fetchSentimentCached,
    staleTime: 30 * 1000,
    refetchInterval: false,
    refetchIntervalInBackground: false,
  })
}

export function useRefreshSentiment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: refreshSentiment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sentiment', 'overview'] })
    },
  })
}
