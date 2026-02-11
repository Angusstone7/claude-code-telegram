import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  LayoutDashboard,
  MessageSquare,
  FolderOpen,
  Files,
  Settings,
  Container,
  Puzzle,
  Terminal,
  GitBranch,
  Users,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'nav.dashboard' },
  { to: '/chat', icon: MessageSquare, label: 'nav.chat' },
  { to: '/projects', icon: FolderOpen, label: 'nav.projects' },
  { to: '/files', icon: Files, label: 'nav.files' },
  { to: '/settings', icon: Settings, label: 'nav.settings' },
  { to: '/docker', icon: Container, label: 'nav.docker' },
  { to: '/plugins', icon: Puzzle, label: 'nav.plugins' },
  { to: '/ssh', icon: Terminal, label: 'nav.ssh' },
  { to: '/gitlab', icon: GitBranch, label: 'nav.gitlab' },
  { to: '/users', icon: Users, label: 'nav.users' },
]

export function Sidebar() {
  const { t } = useTranslation()

  return (
    <aside className="flex h-full w-60 flex-col border-r border-sidebar-border bg-sidebar-background backdrop-blur-[14px] backdrop-saturate-[140%]">
      <div className="flex h-14 items-center border-b border-sidebar-border px-4">
        <span className="text-lg font-bold text-primary">
          Admin Panel
        </span>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-all duration-150',
                isActive
                  ? 'border-l-2 border-primary bg-accent text-primary font-medium'
                  : 'text-sidebar-foreground/70 hover:bg-secondary hover:text-sidebar-foreground',
              )
            }
          >
            <item.icon className="h-4 w-4 shrink-0" />
            <span>{t(item.label)}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
