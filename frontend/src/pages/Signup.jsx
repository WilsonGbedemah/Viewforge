import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Flame } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'

export default function Signup() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [form,    setForm]    = useState({ username: '', password: '', confirm: '' })
  const [error,   setError]   = useState('')
  const [loading, setLoading] = useState(false)

  const f = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (form.password !== form.confirm) {
      setError('Passwords do not match')
      return
    }
    if (form.password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }

    setLoading(true)
    try {
      const res = await api.signup({ username: form.username, password: form.password })
      login(res.access_token, res.username)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err.message)
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-forge-bg flex items-center justify-center px-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="w-9 h-9 bg-forge-red rounded-lg flex items-center justify-center">
            <Flame size={18} className="text-white" />
          </div>
          <span className="text-forge-text font-bold text-2xl tracking-tight">ViewForge</span>
        </div>

        {/* Card */}
        <div className="card space-y-5">
          <div>
            <h1 className="text-forge-text font-semibold text-lg">Create account</h1>
            <p className="text-forge-dim text-sm mt-0.5">Set up your ViewForge access</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Username</label>
              <input
                className="w-full px-3 py-2 text-sm"
                placeholder="your-username"
                value={form.username}
                onChange={f('username')}
                autoFocus
                required
              />
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Password</label>
              <input
                className="w-full px-3 py-2 text-sm"
                type="password"
                placeholder="Min. 6 characters"
                value={form.password}
                onChange={f('password')}
                required
              />
            </div>
            <div>
              <label className="text-xs font-mono text-forge-dim mb-1 block">Confirm password</label>
              <input
                className="w-full px-3 py-2 text-sm"
                type="password"
                placeholder="Repeat password"
                value={form.confirm}
                onChange={f('confirm')}
                required
              />
            </div>

            {error && (
              <p className="text-forge-red text-xs font-mono">{error}</p>
            )}

            <button
              type="submit"
              className="btn-primary w-full mt-1"
              disabled={loading}
            >
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>

          <p className="text-center text-xs text-forge-dim">
            Already have an account?{' '}
            <Link to="/login" className="text-forge-amber hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
