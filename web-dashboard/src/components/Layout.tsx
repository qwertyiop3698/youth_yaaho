import { NavLink, Outlet } from 'react-router-dom'
import { NAV_ITEMS } from '../nav'
import { ApiKeyWidget } from './ApiKeyWidget'

export function Layout() {
  return (
    <div className="flex min-h-screen bg-white text-brand-ink">
      <aside className="w-56 shrink-0 border-r border-brand-border bg-white p-4">
        <h1 className="mb-6 text-lg font-semibold text-brand-ink">Y-SAFE 대시보드</h1>
        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center justify-between rounded px-3 py-2 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue ${
                  isActive ? 'bg-brand-blue text-white' : 'text-gray-700 hover:bg-brand-surface-muted'
                }`
              }
            >
              <span>{item.label}</span>
              {!item.implemented && (
                <span className="ml-2 rounded bg-yellow-100 px-1.5 py-0.5 text-xs text-yellow-700">
                  준비중
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-end border-b border-brand-border bg-white px-6 py-3">
          <ApiKeyWidget />
        </header>
        <main className="flex-1 bg-white p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
