import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchDerivativesOverview, refreshDerivatives } from '../api/client'

export function useDerivatives() {
  return useQuery({
    queryKey: ['derivatives', 'overview'],
    queryFn: fetchDerivativesOverview,
    refetchInterval: false,
    refetchIntervalInBackground: false,
  })
}

export function useRefreshDerivatives() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: refreshDerivatives,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['derivatives', 'overview'] })
    },
  })
}
