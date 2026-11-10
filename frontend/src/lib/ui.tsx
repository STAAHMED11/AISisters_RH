import { createContext, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react'

type ConfirmOpts = { title: string; text?: string; confirmLabel?: string; tone?: 'primary' | 'danger' }
type Toast = { id: number; kind: 'success' | 'error' | 'info'; text: string }
type UI = { confirm: (o: ConfirmOpts) => Promise<boolean>; toast: (text: string, kind?: Toast['kind']) => void }

const Ctx = createContext<UI>({ confirm: async () => true, toast: () => {} })
export const useUI = () => useContext(Ctx)

const BAR: Record<Toast['kind'], string> = { success: 'bg-emerald-400', error: 'bg-rose-400', info: 'bg-mark' }

/** Replaces the browser's alert()/confirm(): a proper dialog and toasts, in the app's own voice. */
export function UIProvider({ children }: { children: ReactNode }) {
  const [dialog, setDialog] = useState<(ConfirmOpts & { resolve: (v: boolean) => void }) | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const seq = useRef(0)

  const confirm = useCallback((o: ConfirmOpts) => new Promise<boolean>(resolve => setDialog({ ...o, resolve })), [])
  const toast = useCallback((text: string, kind: Toast['kind'] = 'info') => {
    const id = ++seq.current
    setToasts(t => [...t, { id, kind, text }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), kind === 'error' ? 8000 : 4000)
  }, [])
  const close = (v: boolean) => { dialog?.resolve(v); setDialog(null) }

  useEffect(() => {
    if (!dialog) return
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') { dialog.resolve(false); setDialog(null) } }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [dialog])

  return (
    <Ctx.Provider value={{ confirm, toast }}>
      {children}
      {dialog && (
        <div className="anim-fade fixed inset-0 z-50 grid place-items-center bg-ink/45 p-4" onMouseDown={e => { if (e.target === e.currentTarget) close(false) }}>
          <div role="dialog" aria-modal="true" aria-label={dialog.title} className="anim-rise float-shadow w-full max-w-md rounded-2xl bg-white p-6">
            <h2 className="font-display text-2xl font-semibold">{dialog.title}</h2>
            {dialog.text && <p className="mt-2 text-[15px] leading-relaxed text-muted">{dialog.text}</p>}
            <div className="mt-6 flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => close(false)}>Annuler</button>
              <button autoFocus className={dialog.tone === 'danger' ? 'btn-danger' : 'btn-primary'} onClick={() => close(true)}>{dialog.confirmLabel ?? 'Confirmer'}</button>
            </div>
          </div>
        </div>
      )}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
        {toasts.map(t => (
          <div key={t.id} role="status" className="anim-rise float-shadow pointer-events-auto flex overflow-hidden rounded-lg bg-ink text-sm text-white">
            <span className={`w-1.5 shrink-0 ${BAR[t.kind]}`} />
            <span className="px-4 py-3 leading-snug">{t.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  )
}
