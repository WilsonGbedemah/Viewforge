import { useEffect, useState } from 'react'
import { api } from '../api'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import { Plus, Trash2, RefreshCw, Edit2 } from 'lucide-react'

const EMPTY = { label: '', email: '', proxy_id: '', watch_style: 'random', notes: '', cookie_data: '' }
const WATCH_STYLES = [
  { value: 'random',  label: 'Random (weighted mix)' },
  { value: 'short',   label: 'Short viewer (mostly brief)' },
  { value: 'medium',  label: 'Medium viewer' },
  { value: 'long',    label: 'Long viewer (mostly full)' },
]

export default function Accounts() {
  const [accounts, setAccounts] = useState([])
  const [proxies,  setProxies]  = useState([])
  const [modal,    setModal]    = useState(null) // null | 'add' | 'edit' | 'proxy'
  const [form,     setForm]     = useState(EMPTY)
  const [selected, setSelected] = useState(null)
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const load = async () => {
    const [a, p] = await Promise.all([api.listAccounts(), api.listProxies()])
    setAccounts(a)
    setProxies(p)
  }

  useEffect(() => { load() }, [])

  const openAdd = () => { setForm(EMPTY); setError(''); setModal('add') }
  const openEdit = (acc) => {
    setSelected(acc)
    setForm({ label: acc.label, email: acc.email, proxy_id: acc.proxy_id || '', watch_style: acc.watch_style || 'random', notes: acc.notes || '', cookie_data: '' })
    setError('')
    setModal('edit')
  }
  const openProxy = () => { setForm(EMPTY); setError(''); setModal('proxy') }

  const handleSave = async () => {
    setLoading(true); setError('')
    try {
      const payload = { ...form, proxy_id: form.proxy_id ? Number(form.proxy_id) : null }
      if (!payload.cookie_data) delete payload.cookie_data
      if (modal === 'add') await api.createAccount(payload)
      else await api.updateAccount(selected.id, payload)
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
        label: form.label, host: form.host, port: Number(form.port),
        username: form.username || null, password: form.password || null,
        protocol: form.protocol || 'http',
      })
      setModal(null)
      await load()
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  const f = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }))

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-forge-text">Accounts</h1>
          <p className="text-forge-dim text-sm font-mono mt-0.5">{accounts.length} registered</p>
        </div>
        <div className="flex gap-2">
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
              <tr><td colSpan={7} className="text-center text-forge-dim py-10 font-mono text-sm">No accounts yet</td></tr>
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

      {/* Add/Edit Account Modal */}
      {(modal === 'add' || modal === 'edit') && (
        <Modal title={modal === 'add' ? 'Add Account' : 'Edit Account'} onClose={() => setModal(null)}>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Label</label>
              <input className="w-full px-3 py-2 text-sm" placeholder="e.g. Account 01" value={form.label} onChange={f('label')} />
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Google Email</label>
              <input className="w-full px-3 py-2 text-sm" placeholder="user@gmail.com" value={form.email} onChange={f('email')} />
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Proxy (optional)</label>
              <select className="w-full px-3 py-2 text-sm" value={form.proxy_id} onChange={f('proxy_id')}>
                <option value="">— None —</option>
                {proxies.map(p => <option key={p.id} value={p.id}>{p.label} ({p.host}:{p.port})</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Viewing Style</label>
              <select className="w-full px-3 py-2 text-sm" value={form.watch_style} onChange={f('watch_style')}>
                {WATCH_STYLES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Cookie JSON (optional)</label>
              <textarea
                className="w-full px-3 py-2 text-xs font-mono h-24 resize-none"
                placeholder='Paste exported cookies as JSON array…'
                value={form.cookie_data}
                onChange={f('cookie_data')}
              />
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Notes</label>
              <input className="w-full px-3 py-2 text-sm" placeholder="Optional notes" value={form.notes} onChange={f('notes')} />
            </div>
            {error && <p className="text-forge-red text-xs font-mono">{error}</p>}
            <div className="flex gap-2 pt-1">
              <button className="btn-primary flex-1" onClick={handleSave} disabled={loading}>
                {loading ? 'Saving…' : 'Save'}
              </button>
              <button className="btn-ghost" onClick={() => setModal(null)}>Cancel</button>
            </div>
          </div>
        </Modal>
      )}

      {/* Add Proxy Modal */}
      {modal === 'proxy' && (
        <Modal title="Add Proxy" onClose={() => setModal(null)}>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Label</label>
              <input className="w-full px-3 py-2 text-sm" placeholder="e.g. US Proxy 1" value={form.label || ''} onChange={f('label')} />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-2">
                <label className="text-xs font-mono text-forge-dim mb-1 block">Host</label>
                <input className="w-full px-3 py-2 text-sm" placeholder="192.168.1.1" value={form.host || ''} onChange={f('host')} />
              </div>
              <div>
                <label className="text-xs font-mono text-forge-dim mb-1 block">Port</label>
                <input className="w-full px-3 py-2 text-sm" type="number" placeholder="8080" value={form.port || ''} onChange={f('port')} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-mono text-forge-dim mb-1 block">Username</label>
                <input className="w-full px-3 py-2 text-sm" placeholder="Optional" value={form.username || ''} onChange={f('username')} />
              </div>
              <div>
                <label className="text-xs font-mono text-forge-dim mb-1 block">Password</label>
                <input className="w-full px-3 py-2 text-sm" type="password" placeholder="Optional" value={form.password || ''} onChange={f('password')} />
              </div>
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Protocol</label>
              <select className="w-full px-3 py-2 text-sm" value={form.protocol || 'http'} onChange={f('protocol')}>
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
