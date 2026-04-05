import { NavLink, Outlet } from 'react-router-dom'

import { ThemeToggle } from './ThemeToggle'

const nav = [
  { to: '/', label: 'Overview' },
  { to: '/contracts', label: 'Contracts' },
  { to: '/data-quality', label: 'Data Quality' },
  { to: '/runs', label: 'Runs' },
  { to: '/schedules', label: 'Schedules' },
  { to: '/settings', label: 'Settings' },
]

export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-[var(--color-surface-elevated)]/90 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-900/90">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-baseline gap-3">
            <NavLink
              to="/"
              className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight text-teal-700 dark:text-teal-400"
            >
              Sraosha
            </NavLink>
            <span className="hidden text-sm text-[var(--color-ink-muted)] sm:inline">
              Contracts &amp; data quality
            </span>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-x-1 gap-y-2">
            <nav className="flex flex-wrap gap-x-1 gap-y-2 text-sm font-medium">
              {nav.map(({ to, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    [
                      'rounded-full px-3 py-1.5 transition-colors',
                      isActive
                        ? 'bg-teal-600 text-white dark:bg-teal-500'
                        : 'text-[var(--color-ink-muted)] hover:bg-stone-200/80 hover:text-[var(--color-ink)] dark:hover:bg-zinc-800 dark:hover:text-zinc-100',
                    ].join(' ')
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-[var(--color-border)] py-6 text-center text-xs text-[var(--color-ink-muted)] dark:border-zinc-800">
        API documentation (same origin as the app in dev via proxy) ·{' '}
        <a className="text-teal-600 underline dark:text-teal-400" href="/docs">
          OpenAPI
        </a>
      </footer>
    </div>
  )
}
