import { useNavigate } from 'react-router-dom'
import { useAutoRefreshSignals, useTradingStatus } from '../hooks/useSignals'
import { SignalCard } from '../components/SignalCard'
import type { EtfSignal } from '../api/types'

function groupEtfByIdx(etfs: EtfSignal[]): Array<[string, EtfSignal[]]> {
  const map = new Map<string, EtfSignal[]>()
  for (const etf of etfs) {
    const key = etf.idx_name || '其他'
    const list = map.get(key)
    if (list) list.push(etf)
    else map.set(key, [etf])
  }
  return Array.from(map.entries())
}

export default function Dashboard() {
  const { data, isLoading, error } = useAutoRefreshSignals()
  const { data: status } = useTradingStatus()
  const navigate = useNavigate()

  if (error) {
    return <div className="text-red-400 text-center py-20">连接后端失败，请确认服务已启动</div>
  }

  if (isLoading || !data) {
    return <div className="text-gray-400 text-center py-20">加载中...</div>
  }

  const etfs = data.etfs as EtfSignal[]
  const highCount = etfs.filter(e => e.signal_level === 'HIGH').length
  const midCount = etfs.filter(e => e.signal_level === 'MID').length

  return (
    <div>
      <div className="flex items-center gap-4 mb-4 text-sm">
        <span className={`px-2 py-1 rounded ${status?.is_trading ? 'bg-green-500/20 text-green-400' : 'bg-gray-800 text-gray-400'}`}>
          {status?.is_trading ? '盘中实时' : '已收盘'}
        </span>
        <span className="text-gray-500">
          模式: {data.mode === 'intraday' ? '盘中信号' : '日度分析'}
        </span>
        <span className="text-gray-500">日期: {data.date}</span>
        {data.updated_at && (
          <span className="text-gray-600">更新: {data.updated_at.split('T')[1]}</span>
        )}
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

      <div className="space-y-5">
        {groupEtfByIdx(etfs).map(([idx, list]) => (
          <section key={idx}>
            <h3 className="flex items-center gap-2 mb-2 text-xs font-medium text-gray-500">
              <span className="inline-block w-1 h-3 rounded-full bg-blue-500" />
              {idx}
              <span className="text-gray-600">{list.length} 只</span>
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              {list.map(etf => (
                <SignalCard
                  key={etf.code}
                  signal={etf}
                  onClick={() => navigate(`/etf/${etf.code}`)}
                />
              ))}
            </div>
          </section>
        ))}
      </div>

      {etfs.length === 0 && (
        <div className="text-gray-500 text-center py-20">
          暂无数据，请等待数据采集或手动运行分析
        </div>
      )}
    </div>
  )
}
