import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchCalendarDays, refreshCalendar } from '../api/client'

export function useCalendarDays(year: number) {
  return useQuery({
    queryKey: ['calendar', 'days', year],
    queryFn: () => fetchCalendarDays(year),
    refetchInterval: false,
    refetchIntervalInBackground: false,
  })
}

export function useRefreshCalendar() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: refreshCalendar,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
    },
  })
}
