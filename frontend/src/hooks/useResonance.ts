import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchResonance, fetchResonanceDay, fetchResonanceV2Signals, fetchResonanceV2Backtest } from '../api/client'

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

export function useResonanceV2(code = '510300') {
  return useQuery({
    queryKey: ['resonanceV2', code],
    queryFn: () => fetchResonanceV2Signals(code),
    placeholderData: keepPreviousData,
    refetchInterval: false,
    refetchIntervalInBackground: false,
  })
}

export function useResonanceV2Backtest(code = '510300') {
  return useQuery({
    queryKey: ['resonanceV2Backtest', code],
    queryFn: () => fetchResonanceV2Backtest(code),
    placeholderData: keepPreviousData,
    staleTime: 10 * 60 * 1000,
    refetchInterval: false,
    refetchIntervalInBackground: false,
  })
}
