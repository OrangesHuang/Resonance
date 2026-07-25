import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import EtfDetail from './pages/EtfDetail'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen w-full px-4 py-6">
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-white">
            ETF 国家队监控
            <span className="ml-2 text-sm font-normal text-gray-400">三因子信号系统</span>
          </h1>
        </header>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/etf/:code" element={<EtfDetail />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
