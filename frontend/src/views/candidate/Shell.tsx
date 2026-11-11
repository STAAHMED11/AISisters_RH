'use client'
import { type ReactNode, useEffect } from 'react'

export default function Shell({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  // dark page: also paint the area behind it (overscroll, address-bar resize on phones)
  useEffect(() => { const prev = document.body.style.background; document.body.style.background = '#07151d'; return () => { document.body.style.background = prev } }, [])
  return (
    <div className="relative flex min-h-dvh flex-col bg-slate-950 text-slate-100"
      style={{ backgroundImage: 'radial-gradient(60rem 40rem at 50% -10%, rgba(27,111,149,.42), transparent 60%), radial-gradient(40rem 30rem at 90% 110%, rgba(255,228,92,.07), transparent 60%)' }}>
      <header className="flex items-center gap-2 px-6 py-5">
        <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="7" fill="#fff" fillOpacity=".12" /><rect x="7" y="8" width="18" height="3.4" rx="1.7" fill="#fff" /><rect x="7" y="14.3" width="13" height="3.4" rx="1.7" fill="#FFE45C" /><rect x="7" y="20.6" width="9" height="3.4" rx="1.7" fill="#fff" opacity=".7" /></svg>
        <span className="font-display text-xl font-semibold tracking-wide text-slate-200">Orvane</span>
      </header>
      <main className={`mx-auto flex w-full flex-1 flex-col px-5 pb-8 ${wide ? 'max-w-3xl' : 'max-w-xl'}`}>{children}</main>
    </div>
  )
}
