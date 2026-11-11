'use client'
import type { ReactNode } from 'react'

export type Tone = 'neutral' | 'good' | 'bad' | 'warn' | 'info'
export type Described = { icon: string; tone: Tone; text: ReactNode; hot?: boolean }

const TRIAGE: Record<string, string> = { yes: 'pré-qualifié', maybe: 'à examiner', no: 'refus proposé' }
const KIND: Record<string, string> = { invite: "l'invitation au pré-entretien", rejection: 'le courrier de refus', acceptance: 'le courrier de rendez-vous' }
const PROPOSAL: Record<string, string> = { accept: 'retenir', reject: 'refuser', review: 'examiner' }
const RECO: Record<string, string> = { invite: 'mérite un rendez-vous', hold: 'à examiner', decline: 'ne correspond pas' }

/** Turns a stored audit event into a sentence a recruiter understands. */
export function describeEvent(e: { action: string; actor: string; payload?: any }): Described {
  const p = e.payload || {}
  switch (e.action) {
    case 'cv_uploaded': return { icon: '📄', tone: 'neutral', text: <>CV déposé</> }
    case 'cv_reprocess': return { icon: '🔄', tone: 'neutral', text: <>Nouvelle analyse du CV demandée</> }
    case 'cv_screened': return { icon: '🧠', tone: p.triage === 'yes' ? 'good' : p.triage === 'no' ? 'bad' : 'warn', hot: !!p.injection,
      text: <>CV analysé : <b>{TRIAGE[p.triage] ?? p.triage}</b> (score {Math.round((p.score ?? 0) * 100)}/100){p.injection ? <span className="ml-2 badge bg-amber-100 text-amber-800">tentative d'injection</span> : null}</> }
    case 'retriage': return { icon: '⚖️', tone: 'info', text: <>Règles de tri réappliquées : {TRIAGE[p.old] ?? p.old} → <b>{TRIAGE[p.new] ?? p.new}</b></> }
    case 'interview_plan_built': return { icon: '🗒', tone: 'info', text: <>Plan de pré-entretien préparé ({p.questions} questions)</> }
    case 'interview_invited': return { icon: '✉️', tone: 'neutral', text: <>Pré-entretien ouvert</> }
    case 'interview_extended': return { icon: '⏳', tone: 'neutral', text: <>Lien de pré-entretien prolongé</> }
    case 'interview_consent': return { icon: '✅', tone: 'neutral', text: <>Consentement donné ({p.mode === 'voice' ? 'vocal' : 'écrit'}, {p.language})</> }
    case 'interview_ended': return { icon: '🎙', tone: 'neutral', text: <>Pré-entretien terminé ({p.mode === 'voice' ? 'vocal' : 'écrit'})</> }
    case 'interview_scored': return { icon: '📊', tone: 'info', text: <>Pré-entretien noté : <b>{p.note}/10</b> — {RECO[p.recommendation] ?? p.recommendation}</> }
    case 'decision': return { icon: p.decision === 'accept' ? '👍' : '👎', tone: p.decision === 'accept' ? 'good' : 'bad',
      text: <><b>{e.actor}</b> {p.decision === 'accept' ? 'a retenu le candidat' : 'a refusé le candidat'}{p.comment ? <span className="text-muted"> — « {p.comment} »</span> : null}</> }
    case 'decision_override': return { icon: '⚠️', tone: 'warn', hot: true,
      text: <><b>{e.actor}</b> a décidé <b>contre la proposition de l'IA</b> ({PROPOSAL[p.ai_proposed] ?? p.ai_proposed}) : {p.decision === 'accept' ? 'retenu' : 'refusé'}<span className="text-muted"> — « {p.comment} »</span></> }
    case 'message_drafted': return { icon: '📝', tone: 'info', text: <>Brouillon préparé : {KIND[p.kind] ?? p.kind}</> }
    case 'message_edited': return { icon: '✏️', tone: 'neutral', text: <>Courrier modifié par le recruiter</> }
    case 'message_approved': return { icon: '👁', tone: 'neutral', text: <>Courrier approuvé ({KIND[p.kind] ?? p.kind}){p.automatic ? ' · envoi automatique' : p.batch ? ' · en lot' : ''}</> }
    case 'message_sent': case 'message_sent_mock': return { icon: '📤', tone: 'good', text: <>Courrier envoyé à <span className="text-muted">{p.to || 'sans adresse'}{p.transport === 'mock' ? ' (simulé)' : ''}</span></> }
    default: return { icon: '•', tone: 'neutral', text: <>{e.action}</> }
  }
}
