import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/common/Layout'
import Dashboard from './pages/Dashboard'
import EtfDetail from './pages/EtfDetail'
import Sentiment from './pages/Sentiment'
import TradeCalendar from './pages/TradeCalendar'
import Resonance from './pages/Resonance'
import KlineCompare from './pages/KlineCompare'
import PortfolioBacktest from './pages/PortfolioBacktest'
import DataManage from './pages/DataManage'
import ScheduledTasks from './pages/ScheduledTasks'
import Methodology from './pages/Methodology'
import PolicyBackdrop from './pages/PolicyBackdrop'
import MacroLeverage from './pages/MacroLeverage'
import RealRate from './pages/RealRate'
import HouseholdGov from './pages/HouseholdGov'
import Response from './pages/Response'

export default function App() {
  return (
    <BrowserRouter basename={__APP_BASE__ || undefined}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/resonance" replace />} />
          <Route path="/monitor" element={<Dashboard />} />
          <Route path="/etf/:code" element={<EtfDetail />} />
          <Route path="/resonance" element={<Resonance />} />
          <Route path="/compare" element={<KlineCompare />} />
          <Route path="/portfolio" element={<PortfolioBacktest />} />
          <Route path="/sentiment" element={<Sentiment />} />
          <Route path="/calendar" element={<TradeCalendar />} />
          <Route path="/data" element={<DataManage />} />
          <Route path="/tasks" element={<ScheduledTasks />} />
          <Route path="/framework" element={<Methodology />} />
          <Route path="/policy" element={<PolicyBackdrop />} />
          <Route path="/macro" element={<MacroLeverage />} />
          <Route path="/real-rate" element={<RealRate />} />
          <Route path="/household" element={<HouseholdGov />} />
          <Route path="/response" element={<Response />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
