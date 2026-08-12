import { useNavigate } from 'react-router-dom'
import { SignalCard } from './SignalCard'
import { useFavorites } from '../hooks/useFavorites'
import type { EtfSignal } from '../api/types'

export default function EtfSignalGrid({ etfs }: { etfs: EtfSignal[] }) {
  const navigate = useNavigate()
  const { favorites, toggleFavorite } = useFavorites()

  if (etfs.length === 0) {
    return (
      <div className="text-gray-500 text-center py-20">
        暂无数据，请等待数据采集或手动运行分析
      </div>
    )
  }

  const favEtfs = etfs.filter(e => favorites.includes(e.code))
  const otherEtfs = etfs.filter(e => !favorites.includes(e.code))

  const renderGrid = (list: EtfSignal[]) => (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      {list.map(etf => (
        <SignalCard
          key={etf.code}
          signal={etf}
          favorite={favorites.includes(etf.code)}
          onToggleFavorite={() => toggleFavorite(etf.code)}
          onClick={() => navigate(`/etf/${etf.code}`)}
        />
      ))}
    </div>
  )

  return (
    <div className="space-y-5">
      {favEtfs.length > 0 && (
        <section>
          <h3 className="flex items-center gap-2 mb-2 text-xs font-medium text-gray-500">
            <span className="text-amber-400">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
              </svg>
            </span>
            收藏
            <span className="text-gray-600">{favEtfs.length} 只</span>
          </h3>
          {renderGrid(favEtfs)}
        </section>
      )}
      <section>
        <h3 className="flex items-center gap-2 mb-2 text-xs font-medium text-gray-500">
          <span className="inline-block w-1 h-3 rounded-full bg-blue-500" />
          {favEtfs.length > 0 ? '其他' : '全部'}
          <span className="text-gray-600">{otherEtfs.length} 只</span>
        </h3>
        {renderGrid(otherEtfs)}
      </section>
    </div>
  )
}
