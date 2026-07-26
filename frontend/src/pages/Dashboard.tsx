import { useAutoRefreshSignals, useTradingStatus, useRefreshEtf } from '../hooks/useSignals'
import EtfSignalGrid from '../components/EtfSignalGrid'
import type { EtfSignal } from '../api/types'

export default function Dashboard() {
  const { data, isLoading, error } = useAutoRefreshSignals()
  const { data: status } = useTradingStatus()
  const refresh = useRefreshEtf()

  const etfs = (data?.etfs ?? []) as EtfSignal[]
  const highCount = etfs.filter(e => e.signal_level === 'HIGH').length
  const midCount = etfs.filter(e => e.signal_level === 'MID').length

  return (
    <div>
      <div className="flex items-center gap-4 mb-4 text-sm">
        <span className={`px-2 py-1 rounded ${status?.is_trading ? 'bg-green-500/20 text-green-400' : 'bg-gray-800 text-gray-400'}`}>
          {status?.is_trading ? '盘中实时' : '已收盘'}
        </span>
        <span className="text-gray-500">
          模式: {data?.mode === 'intraday' ? '盘中信号' : '日度分析'}
        </span>
        <span className="text-gray-500">日期: {data?.date}</span>
        {data?.updated_at && (
          <span className="text-gray-600">更新: {data.updated_at.split('T')[1]}</span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {refresh.isSuccess && refresh.data && (
            <span className="text-xs text-gray-500">
              已刷新 {refresh.data.count} 只{refresh.data.date ? `（${refresh.data.date}）` : ''}
            </span>
          )}
          <button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            className="px-3 py-1.5 rounded text-sm bg-gray-800 text-gray-200 border border-gray-700 hover:border-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {refresh.isPending ? '刷新中…' : '手动刷新'}
          </button>
        </div>
      </div>

      {(highCount > 0 || midCount > 0) && (
        <div className={`mb-4 p-3 rounded-lg border ${
          highCount > 0 ? 'bg-red-500/10 border-red-500/30' : 'bg-amber-500/10 border-amber-500/30'
        }`}>
          <span className="text-sm font-medium">
            {highCount > 0
              ? `${highCount} 只 ETF 触发高确信信号${midCount > 0 ? `，${midCount} 只中等` : ''}`
              : `${midCount} 只 ETF 中等关注`}
          </span>
        </div>
      )}

      {error ? (
        <div className="text-red-400 text-center py-20">连接后端失败，请确认服务已启动</div>
      ) : isLoading || !data ? (
        <div className="text-gray-400 text-center py-20">加载中...</div>
      ) : (
        <EtfSignalGrid etfs={etfs} />
      )}
    </div>
  )
}
