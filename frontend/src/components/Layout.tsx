'use client'
import type { ReactNode } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { api } from '../api'
import { Avatar } from './ui'

const I = (d: string) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d={d} /></svg>
)
const ICON = {
  jobs: I('M3 7h18v12H3zM8 7V5a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M3 12h18'),
  overview: I('M4 4h7v7H4zM13 4h7v4h-7zM13 11h7v9h-7zM4 14h7v6H4z'),
  people: I('M16 11a4 4 0 1 0-8 0 4 4 0 0 0 8 0zM4 20c0-3.3 3.6-5 8-5s8 1.7 8 5'),
  mail: I('M3 6h18v12H3zM3 7l9 6 9-6'),
  cost: I('M12 3v18M16.5 7.5C15.5 6.5 14 6 12 6c-2.5 0-4 1-4 2.6 0 4 8.5 1.8 8.5 6 0 1.7-1.7 2.9-4.5 2.9-2 0-3.8-.6-4.8-1.8'),
}

const Mark = () => (
  <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden>
    <rect width="32" height="32" rx="7" fill="#fff" fillOpacity=".12" />
    <rect x="7" y="8" width="18" height="3.4" rx="1.7" fill="#fff" />
    <rect x="7" y="14.3" width="13" height="3.4" rx="1.7" fill="#FFE45C" />
    <rect x="7" y="20.6" width="9" height="3.4" rx="1.7" fill="#fff" opacity=".7" />
  </svg>
)

/** Same rule as an "active" nav link: exact match with `end`, otherwise the path or one of its sub-paths. */
function useActive(to: string, end?: boolean) {
  const path = usePathname()
  return end ? path === to : path === to || path.startsWith(to + '/')
}

function Item({ to, icon, children, end }: { to: string; icon: ReactNode; children: ReactNode; end?: boolean }) {
  const isActive = useActive(to, end)
  return (
    <Link href={to} aria-current={isActive ? 'page' : undefined}
      className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[15px] transition-colors ${isActive ? 'bg-white/10 font-semibold text-white' : 'text-white/70 hover:bg-white/5 hover:text-white'}`}>
      {isActive && <span className="absolute -left-3 top-1.5 h-6 w-1 rounded-r bg-mark" />}
      {icon}{children}
    </Link>
  )
}

function TopLink({ to, children }: { to: string; children: ReactNode }) {
  const isActive = useActive(to)
  return <Link href={to} className={`rounded-md px-2.5 py-1 ${isActive ? 'bg-white/15' : 'text-white/70'}`}>{children}</Link>
}

export default function Layout({ user, children }: { user: string; children: ReactNode }) {
  const pathname = usePathname()
  const job = pathname.match(/^\/(?:jobs|costs)\/(\d+)/)?.[1]
  // Full reload: the auth gate in the (recruiter) layout re-checks the session and shows the login screen.
  const logout = async () => { await api('/logout', { method: 'POST' }); window.location.assign('/jobs') }

  return (
    <div className="min-h-screen lg:pl-60">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col bg-[#08293a] px-3 py-5 lg:flex">
        <Link href="/jobs" className="mb-7 flex items-center gap-3 px-2 text-white">
          <Mark />
          <span className="leading-none"><span className="font-display block text-2xl font-semibold tracking-wide">Orvane</span><span className="text-xs text-white/60">Recrutement</span></span>
        </Link>
        <nav className="space-y-1">
          <Item to="/jobs" end icon={ICON.jobs}>Offres</Item>
        </nav>
        {job && (
          <div className="mt-6">
            <div className="mb-1 px-3 text-xs font-medium text-white/50">Offre en cours</div>
            <nav className="space-y-1">
              <Item to={`/jobs/${job}`} end icon={ICON.overview}>Vue d'ensemble</Item>
              <Item to={`/jobs/${job}/candidates`} icon={ICON.people}>Candidats</Item>
              <Item to={`/jobs/${job}/outbox`} icon={ICON.mail}>Courriers</Item>
              <Item to={`/costs/${job}`} icon={ICON.cost}>Coût de l'offre</Item>
            </nav>
          </div>
        )}
        <div className="mt-auto flex items-center gap-3 rounded-lg px-2 py-2 text-white">
          <Avatar name={user} size={32} />
          <div className="min-w-0 flex-1 leading-tight"><div className="truncate text-sm font-medium">{user}</div>
            <button onClick={logout} className="text-xs text-white/60 hover:text-white hover:underline">Se déconnecter</button></div>
        </div>
      </aside>

      <header className="sticky top-0 z-20 flex items-center gap-4 bg-[#08293a] px-4 py-3 text-white lg:hidden">
        <Link href="/jobs" className="flex items-center gap-2"><Mark /><span className="font-display text-xl font-semibold">Orvane</span></Link>
        <nav className="ml-2 flex gap-1 text-sm">
          <TopLink to="/jobs">Offres</TopLink>
        </nav>
        <button onClick={logout} className="ml-auto text-xs text-white/70">Quitter</button>
      </header>

      <main className="mx-auto max-w-[1180px] px-5 py-7 sm:px-8 lg:px-10 lg:py-9">{children}</main>
    </div>
  )
}
