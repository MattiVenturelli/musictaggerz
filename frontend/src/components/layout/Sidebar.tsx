import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Disc3, Settings, Wifi, WifiOff, Music } from 'lucide-react'
import { useNotificationStore } from '@/store/useNotificationStore'
import { cn } from '@/utils'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/albums', icon: Disc3, label: 'Albums' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export function Sidebar() {
  const wsConnected = useNotificationStore((s) => s.wsConnected)

  return (
    <aside className="fixed inset-y-0 left-0 w-64 bg-surface-200 border-r border-surface-400 flex flex-col z-40">
      <div className="flex items-center gap-3 px-6 h-16 border-b border-surface-400">
        <Music className="h-7 w-7 text-accent-mauve" />
        <span className="text-lg font-bold text-text tracking-tight">MusicTaggerz</span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-accent-blue/15 text-accent-blue'
                  : 'text-text-muted hover:text-text hover:bg-surface-400/50'
              )
            }
          >
            <Icon className="h-5 w-5" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-3 border-t border-surface-400">
        <div className="flex items-center gap-2 text-xs">
          {wsConnected ? (
            <>
              <Wifi className="h-3.5 w-3.5 text-accent-green" />
              <span className="text-accent-green">Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="h-3.5 w-3.5 text-accent-red" />
              <span className="text-accent-red">Disconnected</span>
            </>
          )}
        </div>
      </div>
    </aside>
  )
}
