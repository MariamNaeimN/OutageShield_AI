import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Incidents from './pages/Incidents'
import IncidentDetail from './pages/IncidentDetail'
import TicketDetail from './pages/TicketDetail'
import SnsDetail from './pages/SnsDetail'
import PagerDutyDetail from './pages/PagerDutyDetail'
import Postmortems from './pages/Postmortems'
import Notifications from './pages/Notifications'

import Login from './pages/Login'
import { getCurrentUser, logout, type AuthUser } from './services/auth'

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(getCurrentUser())

  if (!user) {
    return <Login onLogin={(u) => setUser(u)} />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout user={user} onLogout={() => { logout(); setUser(null) }} />}>
          <Route index element={<Dashboard />} />
          <Route path="incidents" element={<Incidents />} />
          <Route path="incidents/:id" element={<IncidentDetail />} />
          <Route path="tickets/:id" element={<TicketDetail />} />
          <Route path="sns/:id" element={<SnsDetail />} />
          <Route path="pagerduty/:id" element={<PagerDutyDetail />} />
          <Route path="postmortems" element={<Postmortems />} />
          <Route path="notifications" element={<Notifications />} />

        </Route>
      </Routes>
    </BrowserRouter>
  )
}
