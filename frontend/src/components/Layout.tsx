import { NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/resonance', label: '多指标共振', end: false },
  { to: '/', label: 'ETF 国家队监控', end: true },
  { to: '/compare', label: 'K线对比', end: false },
  { to: '/portfolio', label: '组合回测', end: false },
  { to: '/sentiment', label: '市场情绪', end: false },
  { to: '/calendar', label: '交易日历', end: false },
  { to: '/data', label: '数据管理', end: false },
]

export default function Layout() {
  return (
    <div className="flex min-h-screen w-full">
      <aside className="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-4 py-5 border-b border-gray-800">
          <h1 className="text-lg font-bold text-white leading-tight">ETF 国家队监控</h1>
          <p className="mt-1 text-xs text-gray-500">三因子信号系统</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block px-3 py-2 rounded text-sm transition-colors ${
                  isActive
                    ? 'bg-gray-800 text-white font-medium'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
          中央汇金 ETF 资金监测
        </div>
      </aside>
      <main className="flex-1 min-w-0 px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
