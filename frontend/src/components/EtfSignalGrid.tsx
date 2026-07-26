import { useNavigate } from 'react-router-dom'
import { SignalCard } from './SignalCard'
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

export default function EtfSignalGrid({ etfs }: { etfs: EtfSignal[] }) {
  const navigate = useNavigate()

  if (etfs.length === 0) {
    return (
      <div className="text-gray-500 text-center py-20">
        暂无数据，请等待数据采集或手动运行分析
      </div>
    )
  }

  return (
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
  )
}
