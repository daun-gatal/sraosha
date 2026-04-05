import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiGet } from '../api/client'
import { PAGE_TITLE, SECTION_TITLE } from '../ui/titleStyles'

type ContractsList = { items: { contract_id: string; title: string }[]; total: number }
type DQSummary = {
  total_checks: number
  healthy: number
  warning: number
  failed: number
  error: number
  overall_pass_rate: number | null
}

export function HomePage() {
  const contracts = useQuery({
    queryKey: ['contracts'],
    queryFn: () => apiGet<ContractsList>('/api/v1/contracts'),
  })
  const dq = useQuery({
    queryKey: ['dq-summary'],
    queryFn: () => apiGet<DQSummary>('/api/v1/data-quality/summary'),
  })

  return (
    <div className="space-y-10">
      <div>
        <h1 className={`${PAGE_TITLE} text-[var(--color-ink)] dark:text-zinc-50`}>
          Overview
        </h1>
        <p className="mt-2 max-w-2xl text-[var(--color-ink-muted)]">
          Governance health for data contracts and database checks. Use the top navigation to drill
          into each area.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Contracts"
          value={contracts.data?.total ?? '—'}
          hint="Registered YAML contracts"
          loading={contracts.isLoading}
          error={contracts.error}
        />
        <StatCard
          title="DQ checks"
          value={dq.data?.total_checks ?? '—'}
          hint="Soda checks configured"
          loading={dq.isLoading}
          error={dq.error}
        />
        <StatCard
          title="Healthy checks"
          value={dq.data?.healthy ?? '—'}
          hint="Latest run passed"
          loading={dq.isLoading}
          error={dq.error}
        />
        <StatCard
          title="Overall pass rate"
          value={
            dq.data?.overall_pass_rate != null
              ? `${Math.round(dq.data.overall_pass_rate * 100)}%`
              : '—'
          }
          hint="Across latest DQ runs"
          loading={dq.isLoading}
          error={dq.error}
        />
      </div>

      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/50">
        <h2 className={SECTION_TITLE}>Quick links</h2>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          <li>
            <Link className="text-teal-700 underline dark:text-teal-400" to="/contracts">
              Manage contracts
            </Link>
          </li>
          <li>
            <Link className="text-teal-700 underline dark:text-teal-400" to="/runs">
              Validation run history
            </Link>
          </li>
          <li>
            <Link className="text-teal-700 underline dark:text-teal-400" to="/schedules">
              Schedules
            </Link>
          </li>
        </ul>
      </section>
    </div>
  )
}

function StatCard(props: {
  title: string
  value: string | number
  hint: string
  loading?: boolean
  error?: Error | null
}) {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/50">
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-ink-muted)]">
        {props.title}
      </p>
      <p className="mt-2 font-[family-name:var(--font-display)] text-3xl font-semibold tabular-nums text-[var(--color-ink)] dark:text-zinc-100">
        {props.loading ? '…' : props.error ? '!' : props.value}
      </p>
      <p className="mt-1 text-sm text-[var(--color-ink-muted)]">{props.hint}</p>
    </div>
  )
}
