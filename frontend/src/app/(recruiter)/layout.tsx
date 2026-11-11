'use client'
import { useEffect, useState } from 'react'
import { api } from '../../api'
import Layout from '../../components/Layout'
import { TH } from '../../components/ui'
import Login from '../../views/Login'

/** Auth gate for every recruiter page: /api/me decides between the login screen and the app shell. */
export default function RecruiterLayout({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<string | null | undefined>(undefined)
  const load = () => api('/me').then(r => setUser(r.name)).catch(() => setUser(null))
  useEffect(() => {
    load()
    api('/health').then(h => { if (h.thresholds) { TH.yes = h.thresholds.yes; TH.maybe = h.thresholds.maybe } }).catch(() => {})
  }, [])

  if (user === undefined) return null
  if (user === null) return <Login onDone={load} />
  return <Layout user={user}>{children}</Layout>
}
