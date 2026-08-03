import type { SignalResponse, EtfHistoryResponse, EtfInfo, RealtimeStatus, StatsResponse, SentimentOverview, SentimentRefreshResult, EtfRefreshResult, CalendarDays, CalendarRefreshResult, ResonanceOverview, ResonanceDayDetail, TradesResponse, DataStatus, JobState, StartJobRequest, StartJobResponse, PortfolioBacktestResponse } from './types'

const BASE = '/api'

async function parseError(res: Response): Promise<Error> {
  let msg = `API error: ${res.status}`
  try {
    const body = await res.json()
    if (body && typeof body.detail === 'string') msg = body.detail
  } catch {
    /* 忽略非 JSON 响应 */
  }
  return new Error(msg)
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw await parseError(res)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const hasBody = body !== undefined
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: hasBody ? { 'Content-Type': 'application/json' } : undefined,
    body: hasBody ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw await parseError(res)
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

export function fetchResonanceTrades(code = '510300'): Promise<TradesResponse> {
  return get(`/resonance/trades?code=${code}`)
}

export function fetchCalendarDays(year: number): Promise<CalendarDays> {
  return get(`/calendar/days?year=${year}`)
}

export function refreshCalendar(): Promise<CalendarRefreshResult> {
  return post('/calendar/refresh')
}

export function fetchDataStatus(): Promise<DataStatus> {
  return get('/data/status')
}

export function fetchPortfolioBacktest(): Promise<PortfolioBacktestResponse> {
  return get('/portfolio/backtest')
}

export function fetchDataJobs(): Promise<JobState[]> {
  return get('/data/jobs')
}

export function startDataJob(req: StartJobRequest): Promise<StartJobResponse> {
  return post('/data/jobs', req)
}

// ========== V2 信号系统 ==========

import type { V2SignalsResponse, V2SignalDayDetail, V2RegimeResponse, V2BacktestResponse } from './types'

export function fetchResonanceV2Signals(code = '510300'): Promise<V2SignalsResponse> {
  return get(`/resonance/v2/signals/${code}`)
}

export function fetchResonanceV2Signal(code: string, date: string): Promise<V2SignalDayDetail> {
  return get(`/resonance/v2/signal?code=${code}&date=${date}`)
}

export function fetchResonanceV2Regime(code = '510300'): Promise<V2RegimeResponse> {
  return get(`/resonance/v2/regime?code=${code}`)
}

export function fetchResonanceV2Backtest(code = '510300'): Promise<V2BacktestResponse> {
  return get(`/resonance/v2/backtest/${code}`)
}

import type { V3TradesResponse } from './types'

export function fetchResonanceV3Trades(code = '510300'): Promise<V3TradesResponse> {
  return get(`/resonance/v3/trades/${code}`)
}

export function fetchResonanceV4Trades(code = '510300'): Promise<V3TradesResponse> {
  return get(`/resonance/v4/trades/${code}`)
}

export function fetchResonanceV5Trades(code = '510300'): Promise<V3TradesResponse> {
  return get(`/resonance/v5/trades/${code}`)
}
