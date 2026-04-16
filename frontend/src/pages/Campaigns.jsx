import { useEffect, useState } from 'react'
import { api } from '../api'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import { Plus, Play, Square, Trash2, Edit2, ChevronDown, ChevronUp, Download } from 'lucide-react'

const ENTRY_OPTS = ['home', 'search', 'suggested', 'channel', 'playlist', 'notification']
const TYPE_OPTS  = [
  { value: 'video',      label: 'Video (standard uploaded)'   },
  { value: 'short',      label: 'Short (vertical)'            },
  { value: 'livestream', label: 'Livestream (live or replay)' },
  { value: 'channel',    label: 'Channel page'                },
  { value: 'playlist',   label: 'Playlist'                    },
]
const COUNTRIES  = [
  { value: 'us', label: 'United States' },
  { value: 'gb', label: 'United Kingdom' },
  { value: 'ca', label: 'Canada' },
  { value: 'au', label: 'Australia' },
  { value: 'de', label: 'Germany' },
  { value: 'fr', label: 'France' },
]

const EMPTY = {
  name: '', target_url: '', target_type: 'video',
  min_watch_seconds: 3600, max_watch_seconds: 5400,
  sessions_per_account_day: 2, total_sessions_target: 100,
  enable_likes: false, enable_comments: false,
  comment_phrases: '', entry_paths: ['home', 'search', 'suggested'],
  search_keywords: '',
  schedule_start: '', schedule_end: '',
  account_ids: [],
  auto_create_accounts: true,
  min_accounts: 5,
  auto_create_country: 'us',
  auto_create_proxy_id: '',
}

function fmtWatch(seconds) {
  if (seconds >= 3600) return `${Math.round(seconds / 60)}m`
  if (seconds >= 60)   return `${Math.round(seconds / 60)}m`
  return `${seconds}s`
}

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([])
  const [accounts,  setAccounts]  = useState([])
  const [proxies,   setProxies]   = useState([])
  const [modal,     setModal]     = useState(false)
  const [editing,   setEditing]   = useState(null)
  const [form,      setForm]      = useState(EMPTY)
  const [expanded,  setExpanded]  = useState(null)
  const [sessions,  setSessions]  = useState({})
  const [error,     setError]     = useState('')
  const [loading,   setLoading]   = useState(false)

  const load = async () => {
    const [c, a, p] = await Promise.all([api.listCampaigns(), api.listAccounts(), api.listProxies()])
    setCampaigns(c)
    setAccounts(a)
    setProxies(p)
  }

  useEffect(() => { load() }, [])

  const openAdd = () => {
    setEditing(null)
    setForm({ ...EMPTY, account_ids: [] })
    setError('')
    setModal(true)
  }

  const openEdit = (c) => {
    setEditing(c)
    setForm({
      name: c.name, target_url: c.target_url, target_type: c.target_type,
      min_watch_seconds: c.min_watch_seconds, max_watch_seconds: c.max_watch_seconds,
      sessions_per_account_day: c.sessions_per_account_day,
      total_sessions_target: c.total_sessions_target,
      enable_likes: c.enable_likes, enable_comments: c.enable_comments,
      comment_phrases: (c.comment_phrases || []).join('\n'),
      entry_paths: c.entry_paths || [],
      search_keywords: c.search_keywords || '',
      schedule_start: c.schedule_start ? c.schedule_start.slice(0, 16) : '',
      schedule_end: c.schedule_end ? c.schedule_end.slice(0, 16) : '',
      account_ids: c.account_ids || [],
      auto_create_accounts: c.auto_create_accounts || false,
      min_accounts: c.min_accounts ?? 3,
      auto_create_country: c.auto_create_country || 'us',
      auto_create_proxy_id: c.auto_create_proxy_id || '',
    })
    setError('')
    setModal(true)
  }

  const handleSave = async () => {
    setLoading(true); setError('')
    try {
      const payload = {
        ...form,
        min_watch_seconds: Number(form.min_watch_seconds),
        max_watch_seconds: Number(form.max_watch_seconds),
        sessions_per_account_day: Number(form.sessions_per_account_day),
        total_sessions_target: Number(form.total_sessions_target),
        min_accounts: Number(form.min_accounts),
        auto_create_proxy_id: form.auto_create_proxy_id ? Number(form.auto_create_proxy_id) : null,
        comment_phrases: form.comment_phrases
          ? form.comment_phrases.split('\n').map(s => s.trim()).filter(Boolean)
          : [],
        search_keywords: form.search_keywords?.trim() || null,
        schedule_start: form.schedule_start ? new Date(form.schedule_start).toISOString() : null,
        schedule_end: form.schedule_end ? new Date(form.schedule_end).toISOString() : null,
      }
      if (editing) await api.updateCampaign(editing.id, payload)
      else await api.createCampaign(payload)
      setModal(false)
      await load()
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  const handleStart = async (id) => {
    try { await api.startCampaign(id); await load() } catch (e) { alert(e.message) }
  }

  const handleStop = async (id) => {
    try { await api.stopCampaign(id); await load() } catch (e) { alert(e.message) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this campaign?')) return
    await api.deleteCampaign(id)
    await load()
  }

  const toggleExpand = async (id) => {
    if (expanded === id) { setExpanded(null); return }
    setExpanded(id)
    if (!sessions[id]) {
      const s = await api.campaignSessions(id)
      setSessions(p => ({ ...p, [id]: s }))
    }
  }

  const toggleEntry = (path) => {
    setForm(p => ({
      ...p,
      entry_paths: p.entry_paths.includes(path)
        ? p.entry_paths.filter(e => e !== path)
        : [...p.entry_paths, path],
    }))
  }

  const toggleAccount = (id) => {
    setForm(p => ({
      ...p,
      account_ids: p.account_ids.includes(id)
        ? p.account_ids.filter(a => a !== id)
        : [...p.account_ids, id],
    }))
  }

  const f = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }))
  const fb = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.checked }))

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-forge-text">Campaigns</h1>
          <p className="text-forge-dim text-sm font-mono mt-0.5">{campaigns.length} total</p>
        </div>
        <button className="btn-primary" onClick={openAdd}>
          <span className="flex items-center gap-1.5"><Plus size={14} />New Campaign</span>
        </button>
      </div>

      {/* Campaign Cards */}
      <div className="space-y-3">
        {campaigns.length === 0 && (
          <div className="card text-center py-12">
            <p className="text-forge-dim font-mono text-sm">No campaigns yet. Create one to get started.</p>
          </div>
        )}
        {campaigns.map(c => {
          const pct = Math.round((c.completed_sessions / Math.max(c.total_sessions_target, 1)) * 100)
          const isExp = expanded === c.id
          return (
            <div key={c.id} className="card p-0 overflow-hidden">
              <div className="px-5 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge status={c.status} />
                      <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                        c.target_type === 'livestream'
                          ? 'bg-red-900/30 text-forge-red'
                          : 'bg-forge-muted text-forge-dim'
                      }`}>
                        {TYPE_OPTS.find(t => t.value === c.target_type)?.label ?? c.target_type}
                      </span>
                    </div>
                    <h3 className="font-semibold text-forge-text truncate">{c.name}</h3>
                    <p className="text-xs font-mono text-forge-dim truncate mt-0.5">{c.target_url}</p>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    {c.status === 'running' ? (
                      <button onClick={() => handleStop(c.id)}
                        className="flex items-center gap-1 px-3 py-1.5 rounded bg-red-900/30 text-forge-red hover:bg-red-900/50 text-xs font-mono transition-colors">
                        <Square size={11} /> Stop
                      </button>
                    ) : (
                      <button onClick={() => handleStart(c.id)} disabled={c.status === 'completed'}
                        className="flex items-center gap-1 px-3 py-1.5 rounded bg-green-900/30 text-forge-green hover:bg-green-900/50 text-xs font-mono transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
                        <Play size={11} /> Start
                      </button>
                    )}
                    <button onClick={() => api.exportSessions(c.id)} title="Export sessions CSV"
                      className="p-1.5 text-forge-dim hover:text-forge-text transition-colors rounded">
                      <Download size={13} />
                    </button>
                    <button onClick={() => openEdit(c)} className="p-1.5 text-forge-dim hover:text-forge-text transition-colors rounded">
                      <Edit2 size={13} />
                    </button>
                    <button onClick={() => handleDelete(c.id)} className="p-1.5 text-forge-dim hover:text-forge-red transition-colors rounded">
                      <Trash2 size={13} />
                    </button>
                    <button onClick={() => toggleExpand(c.id)} className="p-1.5 text-forge-dim hover:text-forge-text transition-colors rounded">
                      {isExp ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    </button>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="mt-3">
                  <div className="flex justify-between text-xs font-mono text-forge-dim mb-1">
                    <span>{c.completed_sessions}/{c.total_sessions_target} sessions</span>
                    <span>{pct}%</span>
                  </div>
                  <div className="h-1 bg-forge-muted rounded-full overflow-hidden">
                    <div className="h-full bg-forge-amber rounded-full transition-all duration-500"
                      style={{ width: `${pct}%` }} />
                  </div>
                </div>

                {/* Config chips */}
                <div className="flex flex-wrap gap-1.5 mt-3">
                  <span className="tag bg-forge-muted text-forge-dim">{fmtWatch(c.min_watch_seconds)}–{fmtWatch(c.max_watch_seconds)} watch</span>
                  <span className="tag bg-forge-muted text-forge-dim">{c.sessions_per_account_day}/day per account</span>
                  {c.enable_likes && <span className="tag bg-blue-900/30 text-forge-blue">likes on</span>}
                  {c.enable_comments && <span className="tag bg-yellow-900/30 text-forge-amber">comments on</span>}
                  {(c.account_ids || []).length > 0 && (
                    <span className="tag bg-forge-muted text-forge-dim">{c.account_ids.length} accounts</span>
                  )}
                  {c.auto_create_accounts && (
                    <span className="tag bg-forge-green/10 text-forge-green border border-forge-green/30">
                      auto-create ≥{c.min_accounts}
                    </span>
                  )}
                  {c.schedule_start && (
                    <span className="tag bg-forge-muted text-forge-dim">
                      starts {new Date(c.schedule_start).toLocaleDateString()}
                    </span>
                  )}
                  {c.schedule_end && (
                    <span className="tag bg-forge-muted text-forge-dim">
                      ends {new Date(c.schedule_end).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>

              {/* Expanded session list */}
              {isExp && (
                <div className="border-t border-forge-border bg-forge-bg/50 px-5 py-3">
                  <p className="text-xs font-mono text-forge-dim uppercase tracking-wider mb-2">Recent Sessions</p>
                  {(sessions[c.id] || []).length === 0 ? (
                    <p className="text-forge-dim text-xs font-mono">No sessions yet</p>
                  ) : (
                    <div className="space-y-1">
                      {(sessions[c.id] || []).slice(0, 10).map(s => (
                        <div key={s.id} className="flex items-center gap-3 text-xs font-mono text-forge-dim">
                          <Badge status={s.status} />
                          <span>Account #{s.account_id}</span>
                          <span>{s.entry_path || '—'}</span>
                          <span>{s.watch_seconds ? `${s.watch_seconds.toFixed(0)}s` : '—'}</span>
                          {s.liked && <span className="text-forge-blue">👍</span>}
                          {s.commented && <span className="text-forge-amber">💬</span>}
                          {s.error_message && <span className="text-forge-red truncate max-w-xs">{s.error_message}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Create/Edit Modal */}
      {modal && (
        <Modal title={editing ? 'Edit Campaign' : 'New Campaign'} onClose={() => setModal(false)} width="max-w-2xl">
          <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
            {/* Basic info */}
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-mono text-forge-dim mb-1 block">Campaign Name</label>
                <input className="w-full px-3 py-2 text-sm" placeholder="e.g. Promo Push Week 1" value={form.name} onChange={f('name')} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-mono text-forge-dim mb-1 block">Target YouTube URL</label>
                <input className="w-full px-3 py-2 text-sm font-mono" placeholder="https://youtube.com/watch?v=…" value={form.target_url} onChange={f('target_url')} />
              </div>
              <div>
                <label className="text-xs font-mono text-forge-dim mb-1 block">Content Type</label>
                <select className="w-full px-3 py-2 text-sm" value={form.target_type} onChange={f('target_type')}>
                  {TYPE_OPTS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                {form.target_type === 'livestream' && (
                  <p className="text-xs font-mono text-forge-amber mt-1">
                    Live mode: sessions join the stream and dwell for the watch duration. No seeking. Live chat scrolling simulated.
                  </p>
                )}
              </div>
              <div>
                <label className="text-xs font-mono text-forge-dim mb-1 block">Total Session Target</label>
                <input className="w-full px-3 py-2 text-sm" type="number" min="1" value={form.total_sessions_target} onChange={f('total_sessions_target')} />
              </div>
            </div>

            {/* Watch time */}
            <div>
              <p className="text-xs font-mono text-forge-dim uppercase tracking-wider mb-2">Watch Time Per Session</p>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-mono text-forge-dim mb-1 block">Min (seconds) <span className="text-forge-dim/60">3600 = 60 min</span></label>
                  <input className="w-full px-3 py-2 text-sm" type="number" min="60" value={form.min_watch_seconds} onChange={f('min_watch_seconds')} />
                </div>
                <div>
                  <label className="text-xs font-mono text-forge-dim mb-1 block">Max (seconds) <span className="text-forge-dim/60">5400 = 90 min</span></label>
                  <input className="w-full px-3 py-2 text-sm" type="number" min="120" value={form.max_watch_seconds} onChange={f('max_watch_seconds')} />
                </div>
                <div>
                  <label className="text-xs font-mono text-forge-dim mb-1 block">Sessions/Account/Day</label>
                  <input className="w-full px-3 py-2 text-sm" type="number" min="1" value={form.sessions_per_account_day} onChange={f('sessions_per_account_day')} />
                </div>
              </div>
            </div>

            {/* Entry paths */}
            <div>
              <p className="text-xs font-mono text-forge-dim uppercase tracking-wider mb-2">Entry Paths</p>
              <div className="flex flex-wrap gap-2">
                {ENTRY_OPTS.map(p => (
                  <button key={p} type="button" onClick={() => toggleEntry(p)}
                    className={`tag cursor-pointer transition-colors ${
                      form.entry_paths.includes(p)
                        ? 'bg-forge-amber/20 text-forge-amber border border-forge-amber/40'
                        : 'bg-forge-muted text-forge-dim border border-transparent'
                    }`}>
                    {p}
                  </button>
                ))}
              </div>
            </div>

            {/* Search keywords */}
            {form.entry_paths.includes('search') && (
              <div>
                <label className="text-xs font-mono text-forge-dim mb-1 block">
                  Search Keywords <span className="text-forge-dim/60">(required for search entry path)</span>
                </label>
                <input
                  className="w-full px-3 py-2 text-sm"
                  placeholder="e.g. best cooking tutorial 2024"
                  value={form.search_keywords}
                  onChange={f('search_keywords')}
                />
              </div>
            )}

            {/* Schedule */}
            <div>
              <p className="text-xs font-mono text-forge-dim uppercase tracking-wider mb-2">Schedule Window (optional)</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-mono text-forge-dim mb-1 block">Start</label>
                  <input className="w-full px-3 py-2 text-sm" type="datetime-local"
                    value={form.schedule_start} onChange={f('schedule_start')} />
                </div>
                <div>
                  <label className="text-xs font-mono text-forge-dim mb-1 block">End</label>
                  <input className="w-full px-3 py-2 text-sm" type="datetime-local"
                    value={form.schedule_end} onChange={f('schedule_end')} />
                </div>
              </div>
            </div>

            {/* Engagement */}
            <div>
              <p className="text-xs font-mono text-forge-dim uppercase tracking-wider mb-2">Engagement (optional)</p>
              <div className="flex gap-4 mb-3">
                <label className="flex items-center gap-2 text-sm text-forge-dim cursor-pointer">
                  <input type="checkbox" checked={form.enable_likes} onChange={fb('enable_likes')} className="accent-forge-amber" />
                  Enable rare likes (~8% chance)
                </label>
                <label className="flex items-center gap-2 text-sm text-forge-dim cursor-pointer">
                  <input type="checkbox" checked={form.enable_comments} onChange={fb('enable_comments')} className="accent-forge-amber" />
                  Enable rare comments (~3% chance)
                </label>
              </div>
              {form.enable_comments && (
                <div>
                  <label className="text-xs font-mono text-forge-dim mb-1 block">Safe Phrases (one per line)</label>
                  <textarea className="w-full px-3 py-2 text-xs font-mono h-20 resize-none"
                    placeholder={"Great video!\nVery informative\nThanks for sharing"}
                    value={form.comment_phrases} onChange={f('comment_phrases')} />
                </div>
              )}
            </div>

            {/* Account pool */}
            <div className="space-y-3 rounded p-3 border border-forge-green/30 bg-forge-green/5">
              <div>
                <span className="text-sm font-medium text-forge-text">Account Pool for this Campaign</span>
                <p className="text-xs text-forge-dim font-mono mt-0.5">
                  Existing accounts are always reused first. New accounts are created automatically only when the pool falls below the target number.
                </p>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-mono text-forge-dim mb-1 block">Number of accounts needed</label>
                  <input className="w-full px-3 py-2 text-sm" type="number" min="1"
                    value={form.min_accounts} onChange={f('min_accounts')} />
                </div>
                <div>
                  <label className="text-xs font-mono text-forge-dim mb-1 block">Phone number country</label>
                  <select className="w-full px-3 py-2 text-sm" value={form.auto_create_country} onChange={f('auto_create_country')}>
                    {COUNTRIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-mono text-forge-dim mb-1 block">Proxy for new accounts</label>
                  <select className="w-full px-3 py-2 text-sm" value={form.auto_create_proxy_id} onChange={f('auto_create_proxy_id')}>
                    <option value="">— None —</option>
                    {proxies.map(p => <option key={p.id} value={p.id}>{p.label} ({p.host}:{p.port})</option>)}
                  </select>
                </div>
              </div>

              <label className="flex items-center gap-2.5 cursor-pointer pt-1">
                <input type="checkbox" checked={form.auto_create_accounts}
                  onChange={fb('auto_create_accounts')} className="accent-forge-green" />
                <span className="text-xs text-forge-dim font-mono">
                  Auto-create missing accounts when campaign starts or pool runs low
                </span>
              </label>
            </div>

            {/* Account assignment */}
            <div>
              <p className="text-xs font-mono text-forge-dim uppercase tracking-wider mb-2">
                Pre-assign Existing Accounts ({form.account_ids.length} selected)
                <span className="ml-2 text-forge-green normal-case font-normal">
                  — optional, leave empty to let the engine fill the pool automatically
                </span>
              </p>
              <div className="grid grid-cols-2 gap-1.5 max-h-32 overflow-y-auto">
                {accounts.map(a => (
                  <label key={a.id} className="flex items-center gap-2 text-sm cursor-pointer px-2 py-1 rounded hover:bg-forge-muted">
                    <input type="checkbox" checked={form.account_ids.includes(a.id)}
                      onChange={() => toggleAccount(a.id)} className="accent-forge-amber" />
                    <span className="text-forge-dim truncate">{a.label}</span>
                    <Badge status={a.status} />
                  </label>
                ))}
                {accounts.length === 0 && (
                  <p className="text-forge-dim text-xs font-mono col-span-2">
                    {form.auto_create_accounts
                      ? 'No accounts yet — the engine will create them when the campaign starts.'
                      : 'No accounts registered'}
                  </p>
                )}
              </div>
            </div>

            {error && <p className="text-forge-red text-xs font-mono">{error}</p>}

            <div className="flex gap-2 pt-1">
              <button className="btn-primary flex-1" onClick={handleSave} disabled={loading}>
                {loading ? 'Saving…' : editing ? 'Update Campaign' : 'Create Campaign'}
              </button>
              <button className="btn-ghost" onClick={() => setModal(false)}>Cancel</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
