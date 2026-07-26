import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import EtfDetail from './pages/EtfDetail'
import Sentiment from './pages/Sentiment'
import TradeCalendar from './pages/TradeCalendar'
import Resonance from './pages/Resonance'
import DataManage from './pages/DataManage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/etf/:code" element={<EtfDetail />} />
          <Route path="/resonance" element={<Resonance />} />
          <Route path="/sentiment" element={<Sentiment />} />
          <Route path="/calendar" element={<TradeCalendar />} />
          <Route path="/data" element={<DataManage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
