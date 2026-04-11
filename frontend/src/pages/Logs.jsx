import { useEffect, useState, useRef } from 'react'
import { api, connectLogStream } from '../api'
import Badge from '../components/Badge'
import { Download, Trash2, RefreshCw, Radio } from 'lucide-react'

const LEVELS = ['', 'info', 'warning', 'error', 'debug']

export default function Logs() {
  const [logs,       setLogs]       = useState([])
  const [campaigns,  setCampaigns]  = useState([])
  const [filter,     setFilter]     = useState({ campaign_id: '', level: '', limit: 200 })
  const [live,       setLive]       = useState(false)
  const [liveLogs,   setLiveLogs]   = useState([])
  const wsRef  = useRef(null)
  const endRef = useRef(null)

  const loadLogs = async () => {
    try {
      const data = await api.listLogs(filter)
      setLogs(data)
    } catch (_) {}
  }

  useEffect(() => {
    api.listCampaigns().then(setCampaigns)
  }, [])

  useEffect(() => { loadLogs() }, [filter])

  // Live WebSocket feed
  useEffect(() => {
    if (live) {
      const ws = connectLogStream((msg) => {
        setLiveLogs(p => [msg, ...p].slice(0, 300))
      })
      wsRef.current = ws
      return () => ws.close()
    } else {
      wsRef.current?.close()
    }
  }, [live])

  useEffect(() => {
    if (live) endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [liveLogs])

  const handleClear = async () => {
    if (!confirm('Clear all logs' + (filter.campaign_id ? ' for this campaign' : '') + '?')) return
    await api.clearLogs(filter.campaign_id || null)
    setLogs([])
    setLiveLogs([])
  }

  const displayed = live ? liveLogs : logs

  const levelColor = (l) => ({
    error:   'text-forge-red',
    warning: 'text-forge-amber',
    info:    'text-forge-blue',
    debug:   'text-forge-dim',
  })[l] || 'text-forge-dim'

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-forge-text">Logs</h1>
          <p className="text-forge-dim text-sm font-mono mt-0.5">{displayed.length} entries shown</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setLive(l => !l)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded text-xs font-mono border transition-all ${
              live
                ? 'border-forge-green/40 bg-green-900/20 text-forge-green'
                : 'border-forge-border bg-forge-muted text-forge-dim hover:text-forge-text'
            }`}
          >
            <Radio size={12} className={live ? 'animate-pulse' : ''} />
            {live ? 'Live On' : 'Go Live'}
          </button>
          <button className="btn-ghost flex items-center gap-1.5" onClick={loadLogs}>
            <RefreshCw size={13} /> Refresh
          </button>
          <button className="btn-ghost flex items-center gap-1.5"
            onClick={() => api.exportLogs(filter.campaign_id || null)}>
            <Download size={13} /> Export CSV
          </button>
          <button className="btn-ghost flex items-center gap-1.5 hover:text-forge-red hover:border-forge-red/40"
            onClick={handleClear}>
            <Trash2 size={13} /> Clear
          </button>
        </div>
      </div>

      {/* Filters */}
      {!live && (
        <div className="card py-3">
          <div className="flex flex-wrap gap-3 items-end">
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Campaign</label>
              <select className="px-3 py-1.5 text-sm"
                value={filter.campaign_id}
                onChange={e => setFilter(p => ({ ...p, campaign_id: e.target.value }))}>
                <option value="">All Campaigns</option>
                {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Level</label>
              <select className="px-3 py-1.5 text-sm"
                value={filter.level}
                onChange={e => setFilter(p => ({ ...p, level: e.target.value }))}>
                {LEVELS.map(l => <option key={l} value={l}>{l || 'All Levels'}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Limit</label>
              <select className="px-3 py-1.5 text-sm"
                value={filter.limit}
                onChange={e => setFilter(p => ({ ...p, limit: Number(e.target.value) }))}>
                {[50, 100, 200, 500].map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Log table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-y-auto max-h-[calc(100vh-280px)]">
          <table className="w-full text-xs font-mono">
            <thead className="sticky top-0 bg-forge-surface z-10">
              <tr className="border-b border-forge-border text-forge-dim uppercase tracking-wider">
                <th className="text-left px-4 py-2.5 w-32">Time</th>
                <th className="text-left px-4 py-2.5 w-20">Level</th>
                <th className="text-left px-4 py-2.5 w-24">Campaign</th>
                <th className="text-left px-4 py-2.5 w-24">Account</th>
                <th className="text-left px-4 py-2.5">Message</th>
              </tr>
            </thead>
            <tbody>
              {displayed.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center text-forge-dim py-12">
                    {live ? 'Waiting for live events…' : 'No logs found'}
                  </td>
                </tr>
              )}
              {displayed.map((log, i) => (
                <tr key={log.id ?? i} className="border-b border-forge-border/30 hover:bg-forge-muted/20 transition-colors">
                  <td className="px-4 py-2 text-forge-dim whitespace-nowrap">
                    {log.created_at
                      ? new Date(log.created_at).toLocaleTimeString()
                      : new Date().toLocaleTimeString()}
                  </td>
                  <td className={`px-4 py-2 font-semibold ${levelColor(log.level)}`}>
                    {log.level}
                  </td>
                  <td className="px-4 py-2 text-forge-dim">
                    {log.campaign_id ? `#${log.campaign_id}` : '—'}
                  </td>
                  <td className="px-4 py-2 text-forge-dim">
                    {log.account_id ? `#${log.account_id}` : '—'}
                  </td>
                  <td className="px-4 py-2 text-forge-text/80">{log.message}</td>
                </tr>
              ))}
              <tr><td ref={endRef} /></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
