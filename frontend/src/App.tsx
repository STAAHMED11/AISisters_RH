import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { api } from './api'
import Layout from './components/Layout'
import { TH } from './components/ui'
import { UIProvider } from './lib/ui'
import Login from './pages/Login'
import Jobs from './pages/Jobs'
import Welcome from './pages/candidate/Welcome'
import Interview from './pages/candidate/Interview'
import Done from './pages/candidate/Done'
import JobDetail from './pages/JobDetail'
import Candidates from './pages/Candidates'
import CandidateDetail from './pages/CandidateDetail'
import Outbox from './pages/Outbox'
import Costs from './pages/Costs'
import CostJob from './pages/CostJob'

export default function App() {
  return <UIProvider><Routing /></UIProvider>
}

function Routing() {
  const loc = useLocation()
  if (loc.pathname.startsWith('/i/')) {
    return (
      <Routes>
        <Route path="/i/:token" element={<Welcome />} />
        <Route path="/i/:token/interview" element={<Interview />} />
        <Route path="/i/:token/done" element={<Done />} />
      </Routes>
    )
  }
  return <RecruiterApp />
}

function RecruiterApp() {
  const [user, setUser] = useState<string | null | undefined>(undefined)
  const load = () => api('/me').then(r => setUser(r.name)).catch(() => setUser(null))
  useEffect(() => { load(); api('/health').then(h => { if (h.thresholds) { TH.yes = h.thresholds.yes; TH.maybe = h.thresholds.maybe } }).catch(() => {}) }, [])

  if (user === undefined) return null
  if (user === null) return <Login onDone={load} />
  return (
    <Routes>
      <Route element={<Layout user={user} />}>
        <Route path="/jobs" element={<Jobs />} />
        <Route path="/jobs/:id" element={<JobDetail />} />
        <Route path="/jobs/:id/candidates" element={<Candidates />} />
        <Route path="/jobs/:id/outbox" element={<Outbox />} />
        <Route path="/candidates/:id" element={<CandidateDetail />} />
        <Route path="/costs" element={<Costs />} />
        <Route path="/costs/:id" element={<CostJob />} />
        <Route path="*" element={<Navigate to="/jobs" replace />} />
      </Route>
    </Routes>
  )
}
