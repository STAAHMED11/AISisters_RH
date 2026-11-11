'use client'
import { useRef, useState } from 'react'
import { ConversationProvider, useConversation } from '@elevenlabs/react'
import { api } from '../../api'
import { T, type Lang } from '../../lib/i18n'
import Orb, { type OrbState } from '../../components/Orb'

type Props = { token: string; lang: Lang; onDone: () => void; onFallbackText: () => void }

export default function VoiceInterview(p: Props) {
  return (
    <ConversationProvider>
      <Inner {...p} />
    </ConversationProvider>
  )
}

function Inner({ token, lang, onDone, onFallbackText }: Props) {
  const t = T[lang]
  const convId = useRef('')
  const finished = useRef(false)
  const lastRole = useRef<'user' | 'agent' | ''>('')
  const [, force] = useState(0)
  const [caption, setCaption] = useState<{ role: string; text: string } | null>(null)
  const [phase, setPhase] = useState<'ready' | 'starting' | 'live'>('ready')
  const [err, setErr] = useState('')
  const [micDenied, setMicDenied] = useState(false)

  const finish = async () => {
    if (finished.current) return
    finished.current = true
    if (convId.current) {
      try { await api(`/public/interview/${token}/voice-ended`, { method: 'POST', json: { conversation_id: convId.current } }) } catch { /* recruiter can re-fetch */ }
    }
    onDone()
  }

  const conv = useConversation({
    onConnect: ({ conversationId }) => { convId.current = conversationId; setPhase('live') },
    onMessage: m => { lastRole.current = m.role; setCaption({ role: m.role, text: m.message }); force(x => x + 1) },
    onDisconnect: () => { if (phase !== 'ready') finish() },
    onError: msg => setErr(String(msg)),
  })

  const start = async () => {
    setPhase('starting'); setErr('')
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true })
      s.getTracks().forEach(tr => tr.stop())
    } catch { setMicDenied(true); setPhase('ready'); return }
    try {
      const s = await api(`/public/interview/${token}/voice-session`)
      conv.startSession({
        signedUrl: s.signed_url, connectionType: 'websocket', dynamicVariables: s.dynamic_variables,
        overrides: { agent: { language: s.language } },
      })
    } catch (e: any) { setErr(e.message); setPhase('ready') }
  }

  const toText = async () => {
    await api(`/public/interview/${token}/consent`, { method: 'POST', json: { language: lang, mode: 'text' } })
    onFallbackText()
  }

  let state: OrbState = 'idle'
  let label = ''
  if (phase === 'starting' || conv.status === 'connecting') { state = 'connecting'; label = t.connecting }
  else if (conv.status === 'connected') {
    if (conv.isSpeaking) { state = 'speaking'; label = t.speaking }
    else if (lastRole.current === 'user') { state = 'thinking'; label = t.thinkingVoice }
    else { state = 'listening'; label = conv.isMuted ? t.muted : t.listening }
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-between py-6">
      <div className="h-6 text-[15px] font-medium text-slate-300">{phase === 'ready' ? '' : label}</div>

      <div className="flex flex-col items-center gap-6">
        <Orb state={state} getInput={() => conv.getInputVolume()} getOutput={() => conv.getOutputVolume()} />
        <p className="min-h-[4.5rem] max-w-md px-2 text-center text-lg leading-snug text-slate-200">
          {phase === 'live' && caption && (
            <span className={caption.role === 'agent' ? 'text-slate-100' : 'text-indigo-300'}>{caption.text}</span>
          )}
        </p>
      </div>

      <div className="flex w-full flex-col items-center gap-3">
        {micDenied && (
          <div className="mb-2 w-full max-w-sm rounded-xl bg-amber-500/10 p-3 text-center text-sm text-amber-200 ring-1 ring-amber-400/30">
            {t.micDenied}
            <button onClick={toText} className="mt-2 block w-full rounded-lg bg-white/10 py-2 font-medium text-white hover:bg-white/15">{t.text}</button>
          </div>
        )}
        {err && <div className="text-center text-sm text-rose-400">{err}</div>}
        {phase !== 'live' ? (
          <>
            <button onClick={start} disabled={phase === 'starting'}
              className="rounded-full bg-indigo-500 px-8 py-4 text-lg font-medium text-white shadow-lg shadow-indigo-500/30 transition hover:bg-indigo-400 disabled:opacity-50">
              🎙 {phase === 'starting' ? t.connecting : t.startCall}
            </button>
            <button onClick={toText} className="text-sm text-slate-400 underline-offset-4 hover:text-slate-200 hover:underline">{t.text}</button>
          </>
        ) : (
          <div className="flex items-center gap-5">
            <button onClick={() => conv.setMuted(!conv.isMuted)} aria-label="mute"
              className={`grid h-14 w-14 place-items-center rounded-full text-xl ring-1 transition ${conv.isMuted ? 'bg-white text-slate-900 ring-white' : 'bg-white/10 ring-white/20 hover:bg-white/15'}`}>
              {conv.isMuted ? '🔇' : '🎙'}
            </button>
            <button onClick={() => conv.endSession()} aria-label="end"
              className="grid h-14 w-14 place-items-center rounded-full bg-rose-500 text-xl shadow-lg shadow-rose-500/30 transition hover:bg-rose-400">✕</button>
          </div>
        )}
      </div>
    </div>
  )
}
