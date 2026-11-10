import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { CostBar, CostLegend, Stat } from '../components/CostBar'
import { PageSkeleton } from '../components/ui'
import { nf, usd } from '../lib/money'

export default function CostJob() {
  const { id } = useParams()
  const [d, setD] = useState<any>(null)
  const [n, setN] = useState(1500)
  const [rate, setRate] = useState<number | null>(null)
  useEffect(() => { api(`/costs/jobs/${id}`).then(x => { setD(x); setRate(Math.round((x.forecast.yes_rate ?? 0.15) * 100)) }) }, [id])
  if (!d) return <PageSkeleton />
  const f = d.forecast
  const yes = (rate ?? 15) / 100
  const lines = [
    ['Analyse des CV', n, f.avg_cv, n * f.avg_cv],
    ['Pré-entretiens', Math.round(n * yes), f.avg_interview, n * yes * f.avg_interview],
    ['Réponses à tous les candidats', n, f.avg_reply, n * f.avg_reply],
  ] as [string, number, number, number][]
  const total = lines.reduce((s, l) => s + l[3], 0)
  const noData = !f.sample_cv

  return (
    <div className="space-y-6">
      <div>
        <Link to="/costs" className="text-sm text-muted hover:text-ink">← Coûts</Link>
        <h1 className="mt-1 font-display text-4xl font-semibold">{d.job.title}</h1>
        <div className="text-sm text-muted">{d.job.ref} · <Link className="hover:text-brand" to={`/jobs/${d.job.id}/candidates`}>voir les candidats</Link></div>
      </div>

      <section className="card p-5">
        <div className="grid items-center gap-6 md:grid-cols-[auto_1fr_1fr]">
          <div><div className="num text-6xl">{usd(d.cost.total)}</div><div className="text-sm text-muted">dépensé pour cette offre</div></div>
          <CostBar cost={d.cost} height={14} />
          <CostLegend cost={d.cost} />
        </div>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Coût par CV analysé" value={usd(d.per_cv)} hint={`${d.cv_analyzed} CV`} />
        <Stat label="Coût par pré-entretien" value={d.interviews ? usd(d.per_interview) : '—'} hint={d.interviews ? `${d.interviews} entretien(s), voix + IA` : 'aucun pour l\'instant'} />
        <Stat label="Minutes de voix" value={d.voice_minutes.toFixed(1)} hint={`${usd(d.cost.voice)} chez ElevenLabs`} />
        <Stat label="Jetons traités" value={nf(d.input_tokens + d.output_tokens)} hint={`${nf(d.input_tokens)} en entrée · ${nf(d.output_tokens)} en sortie`} />
      </div>

      <section className="card p-5">
        <h2 className="font-display text-2xl font-semibold">Prévision pour une offre à grand volume</h2>
        <p className="mb-4 text-sm text-muted">Calculée à partir des coûts moyens mesurés ci-dessus — pas une estimation théorique.</p>
        {noData ? <p className="text-sm text-muted">Analysez au moins un CV pour obtenir une prévision.</p> : (
          <>
            <div className="mb-4 flex flex-wrap gap-6">
              <label className="text-sm">Nombre de candidatures<input type="number" min={1} className="input mt-1 w-40" value={n} onChange={e => setN(Math.max(1, +e.target.value || 1))} /></label>
              <label className="text-sm">Part pré-qualifiée (%)<input type="number" min={0} max={100} className="input mt-1 w-40" value={rate ?? 15} onChange={e => setRate(Math.min(100, Math.max(0, +e.target.value || 0)))} />
                <span className="mt-1 block text-xs text-muted">{f.yes_rate != null ? `mesuré sur cette offre : ${Math.round(f.yes_rate * 100)} %` : 'valeur par défaut'}</span></label>
            </div>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted"><tr><th className="py-2 font-medium">Poste</th><th className="font-medium">Quantité</th><th className="font-medium">Coût unitaire</th><th className="text-right font-medium">Total</th></tr></thead>
              <tbody>
                {lines.map(l => <tr key={l[0]} className="border-t border-line"><td className="py-2">{l[0]}</td><td className="tabular-nums">{nf(l[1])}</td><td className="tabular-nums text-muted">{usd(l[2])}</td><td className="text-right tabular-nums">{usd(l[3])}</td></tr>)}
                <tr className="border-t-2 border-line font-semibold"><td className="py-2.5" colSpan={3}>Coût estimé de l'offre</td><td className="text-right text-lg tabular-nums">{usd(total)}</td></tr>
              </tbody>
            </table>
            <p className="mt-3 text-xs text-muted">Fiabilité : moyennes mesurées sur {f.sample_cv} CV{f.sample_interviews ? ` et ${f.sample_interviews} pré-entretien(s)` : ', sans aucun pré-entretien mesuré (coût d\'entretien à 0)'}. Plus l'échantillon est grand, plus la prévision est solide.</p>
          </>
        )}
      </section>

      <section className="card overflow-x-auto">
        <div className="border-b border-line p-5"><h2 className="font-display text-2xl font-semibold">Détail par type d'appel</h2></div>
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-slate-50 text-left text-xs text-muted"><tr>{['Type d\'appel', 'Modèle', 'Appels', 'Jetons entrée', 'Jetons sortie', 'Coût'].map(h => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead>
          <tbody>
            {d.by_purpose.map((r: any, i: number) => (
              <tr key={i} className="border-t border-line">
                <td className="px-4 py-2.5"><span className="mr-2 inline-block h-2.5 w-2.5 rounded-[3px]" style={{ background: ({ cv: '#2a78d6', interview: '#eb6834', voice: '#1baf7a', other: '#eda100' } as any)[r.group] }} />{r.label}</td>
                <td className="px-4 py-2.5 text-muted">{r.model}</td>
                <td className="px-4 py-2.5 tabular-nums">{r.calls}</td>
                <td className="px-4 py-2.5 tabular-nums text-muted">{r.input_tokens ? nf(r.input_tokens) : '—'}</td>
                <td className="px-4 py-2.5 tabular-nums text-muted">{r.output_tokens ? nf(r.output_tokens) : '—'}</td>
                <td className="px-4 py-2.5 font-medium tabular-nums">{usd(r.cost)}</td>
              </tr>
            ))}
            {!d.by_purpose.length && <tr><td colSpan={6} className="p-8 text-center text-muted">Aucune dépense enregistrée pour cette offre.</td></tr>}
          </tbody>
        </table>
      </section>

      <section className="card overflow-x-auto">
        <div className="border-b border-line p-5"><h2 className="font-display text-2xl font-semibold">Par candidat</h2><p className="text-sm text-muted">Analyse du CV, pré-entretien (IA + voix), courriers.</p></div>
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-slate-50 text-left text-xs text-muted"><tr>{['Candidat', 'Analyse CV', 'Pré-entretien', 'Courriers', 'Total', 'Répartition'].map(h => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead>
          <tbody>
            {d.candidates.map((c: any) => (
              <tr key={c.id} className="border-t border-line hover:bg-slate-50/60">
                <td className="px-4 py-2.5"><Link className="font-medium hover:text-brand" to={`/candidates/${c.id}`}>{c.name}</Link></td>
                <td className="px-4 py-2.5 tabular-nums">{usd(c.cost.cv)}</td>
                <td className="px-4 py-2.5 tabular-nums">{usd(c.cost.interview + c.cost.voice)}</td>
                <td className="px-4 py-2.5 tabular-nums text-muted">{usd(c.cost.other)}</td>
                <td className="px-4 py-2.5 font-semibold tabular-nums">{usd(c.cost.total)}</td>
                <td className="w-40 px-4 py-2.5"><CostBar cost={c.cost} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
