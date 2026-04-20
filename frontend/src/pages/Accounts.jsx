import { useEffect, useState } from 'react'
import { api } from '../api'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import { Plus, Trash2, RefreshCw, Edit2 } from 'lucide-react'

const ACCOUNT_EMPTY = { label: '', email: '', google_password: '', proxy_id: '', watch_style: 'random', notes: '' }
const PROXY_EMPTY   = { label: '', host: '', port: '', username: '', password: '', protocol: 'http' }

const WATCH_STYLES = [
  { value: 'random', label: 'Random (weighted mix)' },
  { value: 'short',  label: 'Short viewer (mostly brief)' },
  { value: 'medium', label: 'Medium viewer' },
  { value: 'long',   label: 'Long viewer (mostly full)' },
]

export default function Accounts() {
  const [accounts,   setAccounts]  = useState([])
  const [proxies,    setProxies]   = useState([])
  const [modal,      setModal]     = useState(null)   // null | 'add' | 'edit' | 'proxy'
  const [accForm,    setAccForm]   = useState(ACCOUNT_EMPTY)
  const [proxyForm,  setProxyForm] = useState(PROXY_EMPTY)
  const [selected,   setSelected]  = useState(null)
  const [error,      setError]     = useState('')
  const [loading,    setLoading]   = useState(false)

  const load = async () => {
    const [a, p] = await Promise.all([api.listAccounts(), api.listProxies()])
    setAccounts(a)
    setProxies(p)
  }

  useEffect(() => { load() }, [])

  // ── Handlers ──────────────────────────────────────────────────────────────

  const openAdd = () => {
    setAccForm(ACCOUNT_EMPTY)
    setError('')
    setModal('add')
  }

  const openEdit = (acc) => {
    setSelected(acc)
    setAccForm({
      label:          acc.label,
      email:          acc.email,
      google_password:'',
      proxy_id:       acc.proxy_id || '',
      watch_style:    acc.watch_style || 'random',
      notes:          acc.notes || '',
    })
    setError('')
    setModal('edit')
  }

  const openProxy = () => { setProxyForm(PROXY_EMPTY); setError(''); setModal('proxy') }

  const handleAddSave = async () => {
    if (!accForm.label.trim()) { setError('Label is required'); return }
    if (!accForm.email.trim()) { setError('Email is required'); return }
    setLoading(true); setError('')
    try {
      await api.createAccount({
        label:          accForm.label.trim(),
        email:          accForm.email.trim(),
        google_password:accForm.google_password.trim() || null,
        proxy_id:       accForm.proxy_id ? Number(accForm.proxy_id) : null,
        watch_style:    accForm.watch_style,
        notes:          accForm.notes.trim() || null,
      })
      setModal(null)
      await load()
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  const handleEditSave = async () => {
    setLoading(true); setError('')
    try {
      const patch = {
        label:       accForm.label,
        proxy_id:    accForm.proxy_id ? Number(accForm.proxy_id) : null,
        watch_style: accForm.watch_style,
        notes:       accForm.notes || null,
      }
      if (accForm.google_password.trim()) patch.google_password = accForm.google_password.trim()
      await api.updateAccount(selected.id, patch)
      setModal(null)
      await load()
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this account?')) return
    await api.deleteAccount(id)
    await load()
  }

  const handleReset = async (id) => {
    await api.resetAccountDaily(id)
    await load()
  }

  const handleAddProxy = async () => {
    setLoading(true); setError('')
    try {
      await api.createProxy({
        label:    proxyForm.label,
        host:     proxyForm.host,
        port:     Number(proxyForm.port),
        username: proxyForm.username || null,
        password: proxyForm.password || null,
        protocol: proxyForm.protocol || 'http',
      })
      setModal(null)
      await load()
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  const af = (k) => (e) => setAccForm(p => ({ ...p, [k]: e.target.value }))
  const pf = (k) => (e) => setProxyForm(p => ({ ...p, [k]: e.target.value }))

  return (
    <div className="p-6 space-y-5 animate-fade-in">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-forge-text">Accounts</h1>
          <p className="text-forge-dim text-sm font-mono mt-0.5">{accounts.length} registered</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-ghost" onClick={openProxy}>
            <span className="flex items-center gap-1.5"><Plus size={14} />Add Proxy</span>
          </button>
          <button className="btn-primary" onClick={openAdd}>
            <span className="flex items-center gap-1.5"><Plus size={14} />Add Account</span>
          </button>
        </div>
      </div>

      {/* Proxy strip */}
      {proxies.length > 0 && (
        <div className="card py-3">
          <p className="text-forge-dim text-xs font-mono mb-2 uppercase tracking-wider">Proxies ({proxies.length})</p>
          <div className="flex flex-wrap gap-2">
            {proxies.map(p => (
              <div key={p.id} className="flex items-center gap-1.5 bg-forge-muted px-2.5 py-1 rounded text-xs font-mono">
                <span className={`w-1.5 h-1.5 rounded-full ${p.is_active ? 'bg-forge-green' : 'bg-forge-dim'}`} />
                <span className="text-forge-text">{p.label}</span>
                <span className="text-forge-dim">{p.host}:{p.port}</span>
                <button onClick={async () => { await api.deleteProxy(p.id); load() }} className="text-forge-dim hover:text-forge-red ml-1">
                  <Trash2 size={10} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-forge-border text-forge-dim text-xs font-mono uppercase tracking-wider">
              <th className="text-left px-4 py-3">Label</th>
              <th className="text-left px-4 py-3">Email</th>
              <th className="text-left px-4 py-3">Proxy</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Style</th>
              <th className="text-left px-4 py-3">Sessions Today</th>
              <th className="text-left px-4 py-3">Last Active</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {accounts.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center text-forge-dim py-10 font-mono text-sm">
                  No accounts yet — click <span className="text-forge-text">+ Add Account</span> to register a Google account
                </td>
              </tr>
            )}
            {accounts.map(acc => (
              <tr key={acc.id} className="border-b border-forge-border/50 hover:bg-forge-muted/30 transition-colors">
                <td className="px-4 py-3 font-medium text-forge-text">{acc.label}</td>
                <td className="px-4 py-3 font-mono text-forge-dim text-xs">{acc.email}</td>
                <td className="px-4 py-3 text-xs font-mono text-forge-dim">
                  {acc.proxy ? `${acc.proxy.host}:${acc.proxy.port}` : '—'}
                </td>
                <td className="px-4 py-3"><Badge status={acc.status} /></td>
                <td className="px-4 py-3 font-mono text-forge-dim text-xs">{acc.watch_style || 'random'}</td>
                <td className="px-4 py-3 font-mono text-forge-dim text-xs text-center">{acc.daily_session_count}</td>
                <td className="px-4 py-3 font-mono text-forge-dim text-xs">
                  {acc.last_active ? new Date(acc.last_active).toLocaleTimeString() : '—'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1 justify-end">
                    <button title="Reset daily count" onClick={() => handleReset(acc.id)}
                      className="p-1.5 text-forge-dim hover:text-forge-amber transition-colors rounded">
                      <RefreshCw size={13} />
                    </button>
                    <button title="Edit" onClick={() => openEdit(acc)}
                      className="p-1.5 text-forge-dim hover:text-forge-text transition-colors rounded">
                      <Edit2 size={13} />
                    </button>
                    <button title="Delete" onClick={() => handleDelete(acc.id)}
                      className="p-1.5 text-forge-dim hover:text-forge-red transition-colors rounded">
                      <Trash2 size={13} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Add Account Modal ── */}
      {modal === 'add' && (
        <Modal title="Add Google Account" onClose={() => setModal(null)}>
          <div className="space-y-3">
            <p className="text-xs text-forge-dim font-mono">
              Register a Google account you have already created. The engine will use it to watch videos.
            </p>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Label <span className="text-forge-red">*</span></label>
              <input className="w-full px-3 py-2 text-sm" placeholder="e.g. Test Account 1"
                value={accForm.label} onChange={af('label')} autoFocus />
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Gmail Address <span className="text-forge-red">*</span></label>
              <input className="w-full px-3 py-2 text-sm font-mono" placeholder="example@gmail.com"
                type="email" value={accForm.email} onChange={af('email')} />
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Google Password</label>
              <input className="w-full px-3 py-2 text-sm" placeholder="Stored securely for auto re-login"
                type="password" value={accForm.google_password} onChange={af('google_password')} />
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Proxy</label>
              <select className="w-full px-3 py-2 text-sm" value={accForm.proxy_id} onChange={af('proxy_id')}>
                <option value="">— None —</option>
                {proxies.map(p => <option key={p.id} value={p.id}>{p.label} ({p.host}:{p.port})</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Viewing Style</label>
              <select className="w-full px-3 py-2 text-sm" value={accForm.watch_style} onChange={af('watch_style')}>
                {WATCH_STYLES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Notes</label>
              <input className="w-full px-3 py-2 text-sm" placeholder="Optional notes"
                value={accForm.notes} onChange={af('notes')} />
            </div>
            {error && <p className="text-forge-red text-xs font-mono">{error}</p>}
            <div className="flex gap-2 pt-1">
              <button className="btn-primary flex-1" onClick={handleAddSave} disabled={loading}>
                {loading ? 'Saving…' : 'Add Account'}
              </button>
              <button className="btn-ghost" onClick={() => setModal(null)}>Cancel</button>
            </div>
          </div>
        </Modal>
      )}

      {/* ── Edit Account Modal ── */}
      {modal === 'edit' && (
        <Modal title="Edit Account" onClose={() => setModal(null)}>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Label</label>
              <input className="w-full px-3 py-2 text-sm" value={accForm.label} onChange={af('label')} />
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Gmail Address</label>
              <input className="w-full px-3 py-2 text-sm font-mono" value={accForm.email}
                readOnly disabled className="w-full px-3 py-2 text-sm font-mono opacity-50 cursor-not-allowed" />
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">New Password <span className="text-forge-dim/60">(leave blank to keep current)</span></label>
              <input className="w-full px-3 py-2 text-sm" type="password" placeholder="Leave blank to keep unchanged"
                value={accForm.google_password} onChange={af('google_password')} />
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Proxy</label>
              <select className="w-full px-3 py-2 text-sm" value={accForm.proxy_id} onChange={af('proxy_id')}>
                <option value="">— None —</option>
                {proxies.map(p => <option key={p.id} value={p.id}>{p.label} ({p.host}:{p.port})</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Viewing Style</label>
              <select className="w-full px-3 py-2 text-sm" value={accForm.watch_style} onChange={af('watch_style')}>
                {WATCH_STYLES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Notes</label>
              <input className="w-full px-3 py-2 text-sm" placeholder="Optional notes" value={accForm.notes} onChange={af('notes')} />
            </div>
            {error && <p className="text-forge-red text-xs font-mono">{error}</p>}
            <div className="flex gap-2 pt-1">
              <button className="btn-primary flex-1" onClick={handleEditSave} disabled={loading}>
                {loading ? 'Saving…' : 'Save'}
              </button>
              <button className="btn-ghost" onClick={() => setModal(null)}>Cancel</button>
            </div>
          </div>
        </Modal>
      )}

      {/* ── Add Proxy Modal ── */}
      {modal === 'proxy' && (
        <Modal title="Add Proxy" onClose={() => setModal(null)}>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Label</label>
              <input className="w-full px-3 py-2 text-sm" placeholder="e.g. US Proxy 1" value={proxyForm.label} onChange={pf('label')} autoFocus />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-2">
                <label className="text-xs font-mono text-forge-dim mb-1 block">Host</label>
                <input className="w-full px-3 py-2 text-sm" placeholder="192.168.1.1" value={proxyForm.host} onChange={pf('host')} />
              </div>
              <div>
                <label className="text-xs font-mono text-forge-dim mb-1 block">Port</label>
                <input className="w-full px-3 py-2 text-sm" type="number" placeholder="8080" value={proxyForm.port} onChange={pf('port')} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-mono text-forge-dim mb-1 block">Username</label>
                <input className="w-full px-3 py-2 text-sm" placeholder="Optional" value={proxyForm.username} onChange={pf('username')} />
              </div>
              <div>
                <label className="text-xs font-mono text-forge-dim mb-1 block">Password</label>
                <input className="w-full px-3 py-2 text-sm" type="password" placeholder="Optional" value={proxyForm.password} onChange={pf('password')} />
              </div>
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Protocol</label>
              <select className="w-full px-3 py-2 text-sm" value={proxyForm.protocol} onChange={pf('protocol')}>
                <option value="http">HTTP</option>
                <option value="socks5">SOCKS5</option>
              </select>
            </div>
            {error && <p className="text-forge-red text-xs font-mono">{error}</p>}
            <div className="flex gap-2 pt-1">
              <button className="btn-primary flex-1" onClick={handleAddProxy} disabled={loading}>
                {loading ? 'Saving…' : 'Add Proxy'}
              </button>
              <button className="btn-ghost" onClick={() => setModal(null)}>Cancel</button>
            </div>
          </div>
        </Modal>
      )}

    </div>
  )
}
