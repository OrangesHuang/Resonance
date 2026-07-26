import type { SignalResponse, EtfHistoryResponse, EtfInfo, RealtimeStatus, StatsResponse, SentimentOverview, SentimentRefreshResult, EtfRefreshResult, CalendarDays, CalendarRefreshResult, ResonanceOverview, ResonanceDayDetail } from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST' })
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

export function fetchEtfList(): Promise<EtfInfo[]> {
  return get('/etf/list')
}

export function refreshEtf(): Promise<EtfRefreshResult> {
  return post('/etf/refresh')
}

export function fetchRealtimeStatus(): Promise<RealtimeStatus> {
  return get('/realtime/status')
}

export function fetchStats(): Promise<StatsResponse> {
  return get('/stats')
}

export function fetchMarketSentiment(): Promise<SentimentOverview> {
  return get('/sentiment/overview')
}

export function refreshSentiment(): Promise<SentimentRefreshResult> {
  return post('/sentiment/refresh')
}

export function fetchResonance(code = '510300'): Promise<ResonanceOverview> {
  return get(`/resonance/overview?code=${code}`)
}

export function fetchResonanceDay(code: string, date: string): Promise<ResonanceDayDetail> {
  return get(`/resonance/day?code=${code}&date=${date}`)
}

export function fetchCalendarDays(year: number): Promise<CalendarDays> {
  return get(`/calendar/days?year=${year}`)
}

export function refreshCalendar(): Promise<CalendarRefreshResult> {
  return post('/calendar/refresh')
}
