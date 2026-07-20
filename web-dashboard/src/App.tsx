import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { NotFound } from './components/NotFound'
import { Overview } from './pages/Overview/Overview'
import { RiskMap } from './pages/RiskMap/RiskMap'
import { PolicyGaps } from './pages/PolicyGaps/PolicyGaps'
import { BudgetSimulator } from './pages/BudgetSimulator/BudgetSimulator'
import { Clusters } from './pages/Clusters/Clusters'
import { BanditStatus } from './pages/BanditStatus/BanditStatus'
import { PolicyFeedback } from './pages/PolicyFeedback/PolicyFeedback'
import { PolicyDemand } from './pages/PolicyDemand/PolicyDemand'
import { ReportExport } from './pages/ReportExport/ReportExport'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Overview />} />
        <Route path="/risk-map" element={<RiskMap />} />
        <Route path="/policy-gaps" element={<PolicyGaps />} />
        <Route path="/budget-simulator" element={<BudgetSimulator />} />
        <Route path="/clusters" element={<Clusters />} />
        <Route path="/bandit-status" element={<BanditStatus />} />
        <Route path="/policy-feedback" element={<PolicyFeedback />} />
        <Route path="/policy-demand" element={<PolicyDemand />} />
        <Route path="/report-export" element={<ReportExport />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export default App
