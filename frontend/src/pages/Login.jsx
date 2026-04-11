import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [form,    setForm]    = useState({ username: '', password: '' })
  const [error,   setError]   = useState('')
  const [loading, setLoading] = useState(false)

  const f = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const res = await api.login(form)
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
        <div className="flex justify-center mb-8">
          <img src="/logo.svg" alt="ViewForge" className="h-9 w-auto" />
        </div>

        {/* Card */}
        <div className="card space-y-5">
          <div>
            <h1 className="text-forge-text font-semibold text-lg">Sign in</h1>
            <p className="text-forge-dim text-sm mt-0.5">Enter your credentials to continue</p>
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
                placeholder="••••••••"
                value={form.password}
                onChange={f('password')}
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
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="text-center text-xs text-forge-dim">
            No account?{' '}
            <Link to="/signup" className="text-forge-amber hover:underline">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
