// 数据管理/后台任务类型
export type JobStatus = 'pending' | 'running' | 'success' | 'failed'

export type JobParam = string | number | boolean

export interface JobState {
  id: string
  task: string
  params: Record<string, JobParam>
  status: JobStatus
  current: number
  total: number
  message: string
  started_at: string | null
  finished_at: string | null
  error: string | null
  result: Record<string, unknown> | null
}

export type DataFlowStep = 'fetch' | 'derive' | 'write' | 'offline' | 'read' | 'delete'

export interface DataFlowItem {
  step: DataFlowStep
  text: string
}

export interface JobDef {
  task: string
  label: string
  defaults: Record<string, number | boolean>
  data_flow?: DataFlowItem[]
}

export interface EtfDailyStats {
  total_records: number
  trading_days: number
  date_range: [string | null, string | null]
  records_with_shares: number
  // 以交易日历为填充槽: 数据区间内应有数据却缺失的交易日(区间拉取截断/中断等成因)
  missing_days?: number
  missing_ranges?: [string, string][]
}

export interface SeriesStats {
  count: number
  range: [string | null, string | null]
}

export interface CalendarStats {
  count: number
  range: [string | null, string | null]
  last_sync: string | null
}

export interface DataSources {
  etf_daily: EtfDailyStats
  turnover: SeriesStats
  margin: SeriesStats
  calendar: CalendarStats
}

export interface SchedulerJobInfo {
  id: string
  next_run: string | null
}

export interface ScheduledTaskInfo {
  id: string
  label: string
  schedule: string
  purpose: string
  data_flow: DataFlowItem[]
  next_run: string | null
  prev_run: string | null
}

export interface DataStatus {
  sources: DataSources
  jobs: JobDef[]
  running: JobState[]
  scheduler: SchedulerJobInfo[]
  defaults: { etf_days: number; shares_days: number; sentiment_days: number }
}

export interface StartJobRequest {
  task: string
  params?: Record<string, JobParam>
}

export interface StartJobResponse {
  job_id: string
}
