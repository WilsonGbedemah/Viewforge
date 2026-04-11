import clsx from 'clsx'

const MAP = {
  idle:      'bg-forge-muted text-forge-dim',
  running:   'bg-green-900/40 text-forge-green',
  cooldown:  'bg-yellow-900/40 text-forge-amber',
  error:     'bg-red-900/40 text-forge-red',
  paused:    'bg-forge-muted text-forge-dim',
  stopped:   'bg-red-900/30 text-red-400',
  completed: 'bg-blue-900/30 text-forge-blue',
  pending:   'bg-forge-muted text-forge-dim',
  failed:    'bg-red-900/40 text-forge-red',
  info:      'bg-blue-900/30 text-forge-blue',
  warning:   'bg-yellow-900/40 text-forge-amber',
  debug:     'bg-forge-muted text-forge-dim',
}

export default function Badge({ status }) {
  return (
    <span className={clsx('tag', MAP[status] || MAP.idle)}>
      {status === 'running' && (
        <span className="w-1.5 h-1.5 rounded-full bg-forge-green animate-pulse-dot inline-block" />
      )}
      {status}
    </span>
  )
}
