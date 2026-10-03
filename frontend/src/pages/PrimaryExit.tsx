import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { useSupplyOverview } from '../hooks/useSupply'
import { buildUnlockOption } from '../components/supply/unlockOption'
import type { UnlockWeek } from '../api/types'

const BOARD_COLOR: Record<string, string> = {
  主板: 'text-blue-400',
  创业板: 'text-amber-400',
  科创板: 'text-pink-400',
  北交所: 'text-emerald-400',
}

function Stat({ label, value, unit, sub }: { label: string; value: string; unit: string; sub?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-2xl font-semibold text-gray-100">
        {value}
        <span className="text-sm text-gray-400 ml-1">{unit}</span>
      </div>
      {sub && <div className="text-[11px] text-gray-500 mt-1">{sub}</div>}
    </div>
  )
}

const TH = 'text-left py-2 pr-3 font-medium whitespace-nowrap text-gray-500'
const TD = 'py-1.5 pr-3 align-top'

export default function PrimaryExit() {
  const { data, isLoading } = useSupplyOverview(12)

  const option = useMemo(
    () => (data ? buildUnlockOption(data.unlock.forward_weeks) : null),
    [data],
  )

  if (isLoading || !data) {
    return <div className="text-gray-400 text-center py-20">加载中...</div>
  }

  const nextWeek: UnlockWeek | undefined = data.unlock.forward_weeks[0]

  return (
    <div className="space-y-5">
      <div className="flex items-baseline gap-3 flex-wrap">
        <h2 className="text-xl font-bold">一级退出监测</h2>
        <span className="text-xs text-gray-500">
          解禁 = 未来抛压供给 · 减持 = 股东实际退出 · IPO = 新增供给节奏（数据更新于 {data.updated ?? '—'}）
        </span>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <Stat label="未来 12 周解禁" value={data.unlock.total_forward_yi.toFixed(0)} unit="亿元"
          sub={`截至 ${data.unlock.horizon}`} />
        <Stat label="最近一周解禁" value={nextWeek ? nextWeek.market_value_yi.toFixed(0) : '—'} unit="亿元"
          sub={nextWeek ? `周起 ${nextWeek.week_start} · ${nextWeek.count} 笔` : ''} />
        <Stat label={`近 ${data.reduction.days} 日减持`} value={data.reduction.total_yi.toFixed(2)} unit="亿元"
          sub={`${data.reduction.count} 笔`} />
        <Stat label="近 12 月 IPO 募资" value={data.ipo.total_funds_yi.toFixed(0)} unit="亿元"
          sub={`${data.ipo.months.reduce((s, m) => s + m.count, 0)} 家发行`} />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-2">未来逐周解禁供给（按板块堆叠）</h3>
        {option ? (
          <ReactECharts option={option} style={{ height: 300 }} notMerge lazyUpdate />
        ) : (
          <div className="text-gray-500 text-center py-10">暂无解禁数据（可在「数据管理」触发「刷新一级退出数据」）</div>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 overflow-x-auto">
          <h3 className="text-sm font-medium text-gray-300 mb-2">大额解禁个股（未来 12 周）</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-800">
                <th className={TH}>解禁日</th><th className={TH}>个股</th><th className={TH}>板块</th>
                <th className={TH}>解禁市值</th><th className={TH}>占流通</th>
              </tr>
            </thead>
            <tbody>
              {data.unlock.top.map(u => (
                <tr key={`${u.date}-${u.code}`} className="border-b border-gray-800/50 last:border-0">
                  <td className={`${TD} text-gray-400 whitespace-nowrap`}>{u.date}</td>
                  <td className={`${TD} text-gray-200 whitespace-nowrap`}>{u.name} <span className="text-gray-600">{u.code}</span></td>
                  <td className={`${TD} ${BOARD_COLOR[u.board] ?? 'text-gray-400'} whitespace-nowrap`}>{u.board}</td>
                  <td className={`${TD} text-red-400 whitespace-nowrap`}>{u.market_value_yi?.toFixed(1)} 亿</td>
                  <td className={`${TD} text-gray-400 whitespace-nowrap`}>{u.ratio_pct?.toFixed(1)}%</td>
                </tr>
              ))}
              {data.unlock.top.length === 0 && <tr><td className={TD} colSpan={5}>暂无</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 overflow-x-auto">
          <h3 className="text-sm font-medium text-gray-300 mb-2">减持最多的个股（近 {data.reduction.days} 日）</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-800">
                <th className={TH}>个股</th><th className={TH}>板块</th><th className={TH}>减持金额</th><th className={TH}>笔数</th>
              </tr>
            </thead>
            <tbody>
              {data.reduction.top.map(r => (
                <tr key={r.code} className="border-b border-gray-800/50 last:border-0">
                  <td className={`${TD} text-gray-200 whitespace-nowrap`}>{r.name} <span className="text-gray-600">{r.code}</span></td>
                  <td className={`${TD} ${BOARD_COLOR[r.board] ?? 'text-gray-400'} whitespace-nowrap`}>{r.board}</td>
                  <td className={`${TD} text-red-400 whitespace-nowrap`}>{r.amount_yi.toFixed(2)} 亿</td>
                  <td className={`${TD} text-gray-400`}>{r.count}</td>
                </tr>
              ))}
              {data.reduction.top.length === 0 && <tr><td className={TD} colSpan={4}>暂无（可在「数据管理」触发刷新）</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 overflow-x-auto">
        <h3 className="text-sm font-medium text-gray-300 mb-2">IPO 发行节奏（近 12 个月）</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-800">
              <th className={TH}>月份</th><th className={TH}>发行家数</th><th className={TH}>募资（亿元）</th>
            </tr>
          </thead>
          <tbody>
            {data.ipo.months.map(m => (
              <tr key={m.month} className="border-b border-gray-800/50 last:border-0">
                <td className={`${TD} text-gray-300`}>{m.month}</td>
                <td className={`${TD} text-gray-300`}>{m.count}</td>
                <td className={`${TD} text-gray-300`}>{m.funds_yi.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-[11px] text-gray-600 leading-relaxed">
        说明：解禁是**未来**的潜在抛压（限售股到期可卖），减持是股东**已经**卖出（多为高管/大股东），IPO 是**新增**股票供给。
        三者共同构成二级市场的筹码供给端——供给放量而承接不足时，往往是「一级退出、二级接盘」的窗口。
        本页仅做供给面提示，不构成买卖建议。
      </p>
    </div>
  )
}
