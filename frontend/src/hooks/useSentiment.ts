import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchMarketSentiment, refreshSentiment } from '../api/client'

export function useSentiment() {
  return useQuery({
    queryKey: ['sentiment', 'overview'],
    queryFn: fetchMarketSentiment,
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
