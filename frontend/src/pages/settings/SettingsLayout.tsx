import { NavLink, Outlet } from 'react-router-dom'
import { PAGE_TITLE } from '../../ui/titleStyles'

const tabs = [
  { to: 'teams', label: 'Teams' },
  { to: 'alerting', label: 'Alerting' },
  { to: 'connections', label: 'Connections' },
]

export function SettingsLayout() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className={PAGE_TITLE}>Settings</h1>
        <p className="mt-1 max-w-2xl text-sm text-[var(--color-ink-muted)]">
          Manage teams, notification profiles, and database connections used by contracts and data quality
          checks.
        </p>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-[var(--color-border)] pb-px dark:border-zinc-800">
        {tabs.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              [
                'rounded-t-lg px-4 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-teal-600 text-white dark:bg-teal-500'
                  : 'text-[var(--color-ink-muted)] hover:bg-stone-100 dark:hover:bg-zinc-800',
              ].join(' ')
            }
          >
            {label}
          </NavLink>
        ))}
      </div>

      <Outlet />
    </div>
  )
}
