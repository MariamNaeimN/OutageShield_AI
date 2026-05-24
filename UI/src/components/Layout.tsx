import { Outlet, NavLink } from 'react-router-dom'
import { Shield, LayoutDashboard, AlertTriangle, FileText, BookOpen, LogOut } from 'lucide-react'
import { type AuthUser } from '../services/auth'

interface Props {
  user: AuthUser
  onLogout: () => void
}

export default function Layout({ user, onLogout }: Props) {
  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-60 min-w-[240px] bg-[#0d1117] border-r border-gray-800 flex flex-col flex-shrink-0 fixed left-0 top-0 bottom-0 z-10 overflow-hidden">
        <div className="p-5 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-purple-600 rounded-lg flex items-center justify-center animate-float shadow-lg shadow-brand-500/20">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <div>
              <span className="text-sm font-bold text-white">OutageShield</span>
              <span className="text-xs text-brand-400 block -mt-0.5">AI</span>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1 mt-2">
          <SidebarLink to="/" icon={<LayoutDashboard className="w-4 h-4" />} label="Dashboard" />
          <SidebarLink to="/incidents" icon={<AlertTriangle className="w-4 h-4" />} label="Incidents" />
          <SidebarLink to="/postmortems" icon={<FileText className="w-4 h-4" />} label="Postmortems" />

          <SidebarLink to="/notifications" icon={<BookOpen className="w-4 h-4" />} label="Notifications" />
        </nav>

        <div className="p-4 border-t border-gray-800">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 bg-blue-900 rounded-full flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-blue-300">{user.name.charAt(0)}</span>
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-gray-300 truncate">{user.name}</p>
                <p className="text-[10px] text-gray-500 truncate">{user.email}</p>
              </div>
            </div>
            <button onClick={onLogout} className="p-1.5 text-gray-500 hover:text-red-400 transition-colors flex-shrink-0" title="Sign out">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-[#0f1419] ml-60">
        <div className="p-6 animate-fade-in-up">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

function SidebarLink({ to, icon, label, badge }: { to: string; icon: React.ReactNode; label: string; badge?: number }) {
  return (
    <NavLink to={to} end={to === '/'} className={({ isActive }) =>
      `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm whitespace-nowrap transition-all duration-200 ${
        isActive
          ? 'bg-blue-900/30 text-blue-400 border-l-2 border-blue-400 pl-[10px] shadow-sm shadow-blue-500/10'
          : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50 hover:translate-x-0.5'
      }`
    }>
      {icon}
      <span className="flex-1">{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse">
          {badge > 99 ? '99+' : badge}
        </span>
      )}
    </NavLink>
  )
}
