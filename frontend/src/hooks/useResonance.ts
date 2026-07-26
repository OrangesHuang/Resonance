import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchResonance, fetchResonanceDay } from '../api/client'

export function useResonance(code = '510300') {
  return useQuery({
    queryKey: ['resonance', code],
    queryFn: () => fetchResonance(code),
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
