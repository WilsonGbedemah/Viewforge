export default function StatsCard({ label, value, sub, accent }) {
  const colors = {
    red:   'text-forge-red',
    amber: 'text-forge-amber',
    green: 'text-forge-green',
    blue:  'text-forge-blue',
    dim:   'text-forge-dim',
  }
  return (
    <div className="card flex flex-col gap-1">
      <p className="text-forge-dim text-xs font-mono uppercase tracking-wider">{label}</p>
      <p className={`text-3xl font-bold tabular-nums ${colors[accent] || 'text-forge-text'}`}>
        {value ?? '—'}
      </p>
      {sub && <p className="text-forge-dim text-xs font-mono">{sub}</p>}
    </div>
  )
}
