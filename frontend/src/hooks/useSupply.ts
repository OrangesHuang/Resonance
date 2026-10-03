import { useQuery } from '@tanstack/react-query'
import { fetchSupplyOverview } from '../api/client'

export function useSupplyOverview(weeks = 8) {
  return useQuery({
    queryKey: ['supply', weeks],
    queryFn: () => fetchSupplyOverview(weeks),
    staleTime: 5 * 60 * 1000,
  })
}
