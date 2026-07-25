import type { SignalResponse, EtfHistoryResponse, RealtimeStatus, StatsResponse } from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export function fetchSignalsToday(): Promise<SignalResponse> {
  return get('/signals/today')
}

export function fetchSignalsByDate(date: string): Promise<SignalResponse> {
  return get(`/signals/${date}`)
}

export function fetchEtfHistory(code: string, days = 60): Promise<EtfHistoryResponse> {
  return get(`/etf/${code}/history?days=${days}`)
}

export function fetchRealtimeStatus(): Promise<RealtimeStatus> {
  return get('/realtime/status')
}

export function fetchStats(): Promise<StatsResponse> {
  return get('/stats')
}
