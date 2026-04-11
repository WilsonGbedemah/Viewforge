import { NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Users, Megaphone, ScrollText, Flame, LogOut } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../context/AuthContext'
import { api } from '../api'

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/accounts',  label: 'Accounts',  icon: Users },
  { to: '/campaigns', label: 'Campaigns', icon: Megaphone },
  { to: '/logs',      label: 'Logs',      icon: ScrollText },
]

export default function Sidebar() {
  const { username, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    try { await api.logout() } catch (_) {}
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside className="w-56 shrink-0 bg-forge-surface border-r border-forge-border flex flex-col">

      {/* Logo */}
      <div className="px-5 py-6 border-b border-forge-border">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 bg-forge-red rounded flex items-center justify-center">
            <Flame size={15} className="text-white" />
          </div>
          <span className="text-forge-text font-bold text-lg tracking-tight">ViewForge</span>
        </div>
        <p className="text-forge-dim text-xs mt-1 font-mono">v1.0.0</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition-all duration-150',
                isActive
                  ? 'bg-forge-muted text-forge-text'
                  : 'text-forge-dim hover:text-forge-text hover:bg-forge-muted/50'
              )
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer — user + logout */}
      <div className="px-3 py-4 border-t border-forge-border space-y-1">
        {/* Logged-in user */}
        <div className="px-3 py-2 rounded bg-forge-muted/40 flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-forge-red/20 flex items-center justify-center shrink-0">
            <span className="text-forge-red text-xs font-bold uppercase">
              {username?.[0] ?? '?'}
            </span>
          </div>
          <span className="text-forge-text text-xs font-mono truncate">{username ?? '—'}</span>
        </div>

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium text-forge-dim hover:text-forge-red hover:bg-red-900/10 transition-all duration-150"
        >
          <LogOut size={16} />
          Logout
        </button>
      </div>
    </aside>
  )
}
