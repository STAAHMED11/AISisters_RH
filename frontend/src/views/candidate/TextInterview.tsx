'use client'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'
import { T, type Lang } from '../../lib/i18n'

type Msg = { role: 'agent' | 'candidate'; text: string }

export default function TextInterview({ token, lang, onDone }: { token: string; lang: Lang; onDone: () => void }) {
  const t = T[lang]
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(true)
  const [err, setErr] = useState('')
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api(`/public/interview/${token}/start`, { method: 'POST' })
      .then(r => setMsgs(r.transcript)).catch(e => setErr(e.message)).finally(() => setBusy(false))
  }, [token])
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])

  const send = async () => {
    const v = text.trim()
    if (!v || busy) return
    setText(''); setBusy(true); setErr('')
    setMsgs(m => [...m, { role: 'candidate', text: v }])
    try {
      const r = await api(`/public/interview/${token}/message`, { method: 'POST', json: { text: v } })
      setMsgs(m => [...m, { role: 'agent', text: r.reply }])
      if (r.done) setTimeout(onDone, 2500)
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  const finish = async () => { await api(`/public/interview/${token}/finish`, { method: 'POST' }); onDone() }

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto py-4">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'agent' ? 'justify-start' : 'justify-end'}`}>
            <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed ${m.role === 'agent' ? 'rounded-bl-md bg-white/10 text-slate-100' : 'rounded-br-md bg-indigo-500 text-white'}`}>{m.text}</div>
          </div>
        ))}
        {busy && <div className="text-sm text-slate-400"><span className="animate-pulse">{t.thinking}</span></div>}
        {err && <div className="text-sm text-rose-400">{err}</div>}
        <div ref={bottom} />
      </div>
      <div className="sticky bottom-0 -mx-1 bg-slate-950/80 pb-2 pt-3 backdrop-blur">
        <div className="flex items-end gap-2 rounded-2xl bg-white/10 p-2 ring-1 ring-white/10 focus-within:ring-indigo-400">
          <textarea rows={1} value={text} onChange={e => setText(e.target.value)} disabled={busy && !msgs.length}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder={t.typeHere} className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-[15px] outline-none placeholder:text-slate-500" />
          <button onClick={send} disabled={busy || !text.trim()} className="rounded-xl bg-indigo-500 px-4 py-2 text-sm font-medium disabled:opacity-40">{t.send}</button>
        </div>
        <button onClick={finish} className="mt-2 w-full text-center text-xs text-slate-500 hover:text-slate-300">{t.end}</button>
      </div>
    </div>
  )
}
