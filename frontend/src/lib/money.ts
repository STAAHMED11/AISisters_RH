/** USD with enough precision for sub-cent amounts (an LLM call often costs a fraction of a cent). */
export function usd(v: number | null | undefined, unit = false): string {
  if (v == null) return '—'
  const a = Math.abs(v)
  const s = a >= 100 ? v.toFixed(0) : a >= 1 ? v.toFixed(2) : a >= 0.01 ? v.toFixed(3) : v.toFixed(4)
  return `$${s}${unit ? '' : ''}`
}
export const pct = (part: number, total: number) => (total > 0 ? Math.round((part / total) * 100) : 0)
export const nf = (n: number) => n.toLocaleString('fr-FR')
