import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiGet } from '../api/client'
import { PAGE_TITLE } from '../ui/titleStyles'

type Check = {
  id: string
  name: string
  latest_status: string | null
  run_count: number
  is_enabled: boolean
}

type Response = { items: Check[]; total: number }

export function DataQualityPage() {
  const q = useQuery({
    queryKey: ['dq-checks'],
    queryFn: () => apiGet<Response>('/api/v1/data-quality'),
  })

  if (q.isLoading) return <p className="text-[var(--color-ink-muted)]">Loading checks…</p>
  if (q.error)
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        {String(q.error)}
      </div>
    )

  const rows = q.data?.items ?? []

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className={PAGE_TITLE}>Data Quality</h1>
          <p className="text-[var(--color-ink-muted)]">
            SodaCL checks against your connections. {rows.length} configured.
          </p>
        </div>
        <Link
          to="/data-quality/new"
          className="rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 dark:bg-teal-500 dark:hover:bg-teal-600"
        >
          New DQ Check
        </Link>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[var(--color-border)] bg-stone-50/50 px-6 py-12 text-center dark:border-zinc-700 dark:bg-zinc-900/20">
          <p className="font-medium text-[var(--color-ink)]">No DQ checks yet</p>
          <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
            Create a check with SodaCL and a saved connection—one screen, optional advanced fields.
          </p>
          <Link
            to="/data-quality/new"
            className="mt-4 inline-block rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 dark:bg-teal-500"
          >
            New DQ Check
          </Link>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-[var(--color-border)] dark:border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[var(--color-border)] bg-stone-100/80 dark:border-zinc-800 dark:bg-zinc-900">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Latest</th>
                <th className="px-4 py-3 font-medium">Runs</th>
                <th className="px-4 py-3 font-medium">Enabled</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)] dark:divide-zinc-800">
              {rows.map((r) => (
                <tr key={r.id} className="dark:bg-zinc-900/20">
                  <td className="px-4 py-3">
                    <Link
                      to={`/data-quality/${r.id}`}
                      className="font-medium text-teal-700 underline-offset-2 hover:underline dark:text-teal-400"
                    >
                      {r.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{r.latest_status ?? '—'}</td>
                  <td className="px-4 py-3 tabular-nums">{r.run_count}</td>
                  <td className="px-4 py-3">{r.is_enabled ? 'yes' : 'no'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
