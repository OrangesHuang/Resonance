import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchSignalsToday, fetchRealtimeStatus, refreshEtf } from '../api/client'

export function useSignals(refetchInterval: number | false = false) {
  return useQuery({
    queryKey: ['signals', 'today'],
    queryFn: fetchSignalsToday,
    refetchInterval,
    refetchIntervalInBackground: false,
  })
}

export function useRefreshEtf() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: refreshEtf,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signals', 'today'] })
    },
  })
}

export function useTradingStatus() {
  return useQuery({
    queryKey: ['realtime', 'status'],
    queryFn: fetchRealtimeStatus,
    refetchInterval: 60000,
  })
}

export function useAutoRefreshSignals() {
  const { data: status } = useTradingStatus()
  const isTrading = status?.is_trading ?? false
  const interval = isTrading ? 30000 : false
  return useSignals(interval)
}
