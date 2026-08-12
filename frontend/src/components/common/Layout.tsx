import { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import useIsMobile from '../../hooks/useIsMobile'

const TOP_NAV = [
  { to: '/resonance', label: 'ETF择时分析' },
  { to: '/compare', label: 'ETF走势对比' },
  { to: '/portfolio', label: '组合回测' },
]

const AUX_NAV = [
  { to: '/sentiment', label: '市场宏观指标' },
  { to: '/monitor', label: 'ETF流向分析' },
  { to: '/derivatives', label: '衍生品数据' },
  { to: '/data', label: '数据管理' },
  { to: '/calendar', label: '交易日历' },
]

const AUX_PATHS = new Set(AUX_NAV.map(i => i.to))

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `block px-3 py-2 rounded text-sm transition-colors ${
    isActive
      ? 'bg-gray-800 text-white font-medium'
      : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
  }`

function SidebarNav() {
  const location = useLocation()
  const [auxOpen, setAuxOpen] = useState(true)

  useEffect(() => {
    if (AUX_PATHS.has(location.pathname)) setAuxOpen(true)
  }, [location.pathname])

  const auxActive = AUX_PATHS.has(location.pathname)

  return (
    <nav className="flex-1 px-3 py-4 space-y-1">
      {TOP_NAV.map(item => (
        <NavLink key={item.to} to={item.to} className={linkClass}>
          {item.label}
        </NavLink>
      ))}
      <button
        onClick={() => setAuxOpen(o => !o)}
        className={`flex w-full items-center justify-between px-3 py-2 rounded text-sm transition-colors ${
          auxActive
            ? 'text-white'
            : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
        }`}
      >
        <span>辅助数据</span>
        <svg
          width="14" height="14" viewBox="0 0 20 20" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round"
          strokeLinejoin="round"
          className={`transition-transform ${auxOpen ? 'rotate-90' : ''}`}
        >
          <polyline points="7 4 13 10 7 16" />
        </svg>
      </button>
      {auxOpen && (
        <div className="space-y-1">
          {AUX_NAV.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/monitor'}
              className={({ isActive }) => `${linkClass({ isActive })} pl-8`}
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      )}
    </nav>
  )
}

function SidebarBrand() {
  return (
    <div className="px-4 py-5 border-b border-gray-800">
      <h1 className="text-lg font-bold text-white leading-tight">ETF买卖分析</h1>
      <p className="mt-1 text-xs text-gray-500">多因子信号系统</p>
    </div>
  )
}

export default function Layout() {
  const isMobile = useIsMobile()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()

  useEffect(() => { setDrawerOpen(false) }, [location.pathname])

  if (!isMobile) {
    return (
      <div className="flex min-h-screen w-full">
        <aside className="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
          <SidebarBrand />
          <SidebarNav />
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

  return (
    <div className="flex flex-col min-h-dvh w-full">
      <header className="sticky top-0 z-30 flex items-center gap-3 bg-gray-900 border-b border-gray-800 px-4 h-12 shrink-0">
        <button
          onClick={() => setDrawerOpen(true)}
          className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          aria-label="打开导航"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="3" y1="5" x2="17" y2="5" />
            <line x1="3" y1="10" x2="17" y2="10" />
            <line x1="3" y1="15" x2="17" y2="15" />
          </svg>
        </button>
        <h1 className="text-sm font-bold text-white truncate">ETF买卖分析</h1>
      </header>

      {drawerOpen && (
        <div className="fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="absolute left-0 top-0 bottom-0 w-64 bg-gray-900 border-r border-gray-800 flex flex-col animate-slide-in">
            <SidebarBrand />
            <SidebarNav />
            <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
              中央汇金 ETF 资金监测
            </div>
          </aside>
        </div>
      )}

      <main className="flex-1 min-w-0 px-3 py-4">
        <Outlet />
      </main>
    </div>
  )
}
