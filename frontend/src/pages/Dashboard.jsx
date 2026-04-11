import { useEffect, useState, useRef } from 'react'
import { api, connectLogStream } from '../api'
import StatsCard from '../components/StatsCard'
import Badge from '../components/Badge'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { Activity, Wifi, WifiOff } from 'lucide-react'

export default function Dashboard() {
  const [stats, setStats]       = useState(null)
  const [campaigns, setCampaigns] = useState([])
  const [liveLogs, setLiveLogs] = useState([])
  const [wsOk, setWsOk]         = useState(false)
  const wsRef = useRef(null)
  const logEndRef = useRef(null)

  // Fetch stats + campaigns
  const refresh = async () => {
    try {
      const [s, c] = await Promise.all([api.stats(), api.listCampaigns()])
      setStats(s)
      setCampaigns(c)
    } catch (_) {}
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 8000)
    return () => clearInterval(interval)
  }, [])

  // WebSocket live logs
  useEffect(() => {
    const ws = connectLogStream((msg) => {
      setWsOk(true)
      setLiveLogs((prev) => [msg, ...prev].slice(0, 120))
    })
    wsRef.current = ws
    ws.onopen = () => setWsOk(true)
    ws.onclose = () => setWsOk(false)
    ws.onerror = () => setWsOk(false)
    return () => ws.close()
  }, [])

  // Build mini chart data from campaigns
  const chartData = campaigns.slice(0, 8).map((c) => ({
    name: c.name.length > 12 ? c.name.slice(0, 12) + '…' : c.name,
    done: c.completed_sessions,
    target: c.total_sessions_target,
  }))

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-forge-text">Dashboard</h1>
          <p className="text-forge-dim text-sm font-mono mt-0.5">System overview</p>
        </div>
        <div className={`flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded border ${
          wsOk ? 'border-forge-green/40 text-forge-green bg-green-900/10'
               : 'border-forge-border text-forge-dim bg-forge-muted'
        }`}>
          {wsOk ? <Wifi size={12} /> : <WifiOff size={12} />}
          {wsOk ? 'Live' : 'Connecting…'}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard label="Total Accounts"    value={stats?.total_accounts}     accent="dim" />
        <StatsCard label="Active Now"        value={stats?.active_accounts}    accent="green"
                   sub={`of ${stats?.total_accounts ?? 0} accounts`} />
        <StatsCard label="Sessions Today"    value={stats?.sessions_today}     accent="amber" />
        <StatsCard label="Total Completed"   value={stats?.completed_sessions} accent="blue" />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard label="Campaigns"         value={stats?.total_campaigns}    accent="dim" />
        <StatsCard label="Running"           value={stats?.running_campaigns}  accent="red" />
        <StatsCard label="Total Sessions"    value={stats?.total_sessions}     accent="dim" />
        <StatsCard label="Failed"            value={stats?.failed_sessions}    accent="red" />
      </div>

      {/* Chart + Live Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Campaign Progress Chart */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={14} className="text-forge-amber" />
            <h3 className="text-sm font-semibold text-forge-text">Campaign Progress</h3>
          </div>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorDone" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#f59b00" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#f59b00" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" tick={{ fill: '#888880', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#888880', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#111', border: '1px solid #1e1e1e', borderRadius: 6, fontSize: 12, fontFamily: 'JetBrains Mono' }}
                  labelStyle={{ color: '#e8e4dc' }}
                  itemStyle={{ color: '#f59b00' }}
                />
                <Area type="monotone" dataKey="done" stroke="#f59b00" strokeWidth={2} fill="url(#colorDone)" name="Completed" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-44 flex items-center justify-center text-forge-dim text-sm font-mono">
              No campaigns yet
            </div>
          )}
        </div>

        {/* Live Log Feed */}
        <div className="card flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-forge-text">Live Logs</h3>
            <span className="text-forge-dim text-xs font-mono">{liveLogs.length} events</span>
          </div>
          <div className="flex-1 overflow-y-auto space-y-1 max-h-48 font-mono text-xs">
            {liveLogs.length === 0 ? (
              <p className="text-forge-dim py-2">Waiting for events…</p>
            ) : (
              liveLogs.map((log, i) => (
                <div key={i} className="flex gap-2 items-start">
                  <span className={`shrink-0 ${
                    log.level === 'error'   ? 'text-forge-red' :
                    log.level === 'warning' ? 'text-forge-amber' :
                    log.level === 'debug'   ? 'text-forge-dim' :
                    'text-forge-blue'
                  }`}>[{log.level}]</span>
                  <span className="text-forge-dim/80 truncate">{log.message}</span>
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>

      {/* Running Campaigns */}
      {campaigns.filter(c => c.status === 'running').length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-forge-text mb-3">Running Campaigns</h3>
          <div className="space-y-3">
            {campaigns.filter(c => c.status === 'running').map(c => {
              const pct = Math.round((c.completed_sessions / Math.max(c.total_sessions_target, 1)) * 100)
              return (
                <div key={c.id}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <Badge status="running" />
                      <span className="text-sm text-forge-text font-medium">{c.name}</span>
                    </div>
                    <span className="text-xs font-mono text-forge-dim">
                      {c.completed_sessions}/{c.total_sessions_target} sessions ({pct}%)
                    </span>
                  </div>
                  <div className="h-1.5 bg-forge-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-forge-amber rounded-full transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
