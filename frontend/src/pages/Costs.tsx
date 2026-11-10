import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { CostBar, CostLegend, Stat } from '../components/CostBar'
import { PageHeader, PageSkeleton } from '../components/ui'
import { nf, usd } from '../lib/money'

export default function Costs() {
  const [d, setD] = useState<any>(null)
  useEffect(() => { api('/costs').then(setD) }, [])
  if (!d) return <PageSkeleton />
  const ivCost = d.cost.interview + d.cost.voice
  return (
    <div className="space-y-6">
      <PageHeader title="Coûts" subtitle="Coûts réels mesurés en dollars : jetons facturés par Anthropic pour chaque appel et minutes facturées par ElevenLabs pour la voix. Le suivi compte l'activité depuis son activation." />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Dépensé au total" value={usd(d.total)} hint={`${nf(d.calls)} appels IA`} />
        <Stat label="Coût moyen d'un CV analysé" value={usd(d.per_cv)} hint={`sur ${d.cv_analyzed} CV`} />
        <Stat label="Coût moyen d'un pré-entretien" value={usd(d.per_interview)} hint={d.interviews ? `voix + IA, sur ${d.interviews} entretien(s)` : 'aucun pré-entretien mesuré'} />
        <Stat label="Pré-entretiens (voix + IA)" value={usd(ivCost)} hint={`dont voix ${usd(d.cost.voice)}`} />
      </div>

      <section className="card p-5">
        <h2 className="mb-1 font-display text-2xl font-semibold">Répartition de la dépense</h2>
        <p className="mb-4 text-sm text-muted">Où part l'argent, toutes offres confondues.</p>
        <div className="grid items-center gap-6 md:grid-cols-[1fr_1fr]">
          <CostBar cost={d.cost} height={14} />
          <CostLegend cost={d.cost} />
        </div>
      </section>

      <section className="card overflow-x-auto">
        <div className="border-b border-line p-5"><h2 className="font-display text-2xl font-semibold">Par offre</h2><p className="text-sm text-muted">Cliquez sur une offre pour le détail et la prévision.</p></div>
        <table className="w-full min-w-[900px] text-sm">
          <thead className="bg-slate-50 text-left text-xs text-muted">
            <tr>{['Offre', 'CV analysés', 'Analyse des CV', 'Par CV', 'Pré-entretiens', 'Pré-entretiens', 'Par entretien', 'Total', 'Répartition'].map((h, i) => <th key={i} className="px-4 py-3 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {d.jobs.map((j: any) => (
              <tr key={j.id} className="border-t border-line align-middle hover:bg-slate-50/60">
                <td className="px-4 py-3"><Link to={`/costs/${j.id}`} className="font-medium hover:text-brand">{j.title}</Link><div className="text-xs text-muted">{j.ref}</div></td>
                <td className="px-4 py-3 tabular-nums">{j.cv_analyzed}</td>
                <td className="px-4 py-3 tabular-nums">{usd(j.cost.cv)}</td>
                <td className="px-4 py-3 tabular-nums text-muted">{j.cv_analyzed ? usd(j.per_cv) : '—'}</td>
                <td className="px-4 py-3 tabular-nums">{j.interviews}</td>
                <td className="px-4 py-3 tabular-nums">{usd(j.cost.interview + j.cost.voice)}</td>
                <td className="px-4 py-3 tabular-nums text-muted">{j.interviews ? usd(j.per_interview) : '—'}</td>
                <td className="px-4 py-3 font-semibold tabular-nums">{usd(j.cost.total)}</td>
                <td className="w-48 px-4 py-3"><CostBar cost={j.cost} /></td>
              </tr>
            ))}
            {!d.jobs.length && <tr><td colSpan={9} className="p-10 text-center text-muted">Aucune offre.</td></tr>}
          </tbody>
        </table>
        {d.deleted_or_unassigned > 0 && <div className="border-t border-line px-5 py-3 text-xs text-muted">+ {usd(d.deleted_or_unassigned)} dépensés pour des offres supprimées.</div>}
      </section>
    </div>
  )
}
