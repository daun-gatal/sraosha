import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../api/client'
import { PAGE_TITLE } from '../ui/titleStyles'

type Row = {
  contract_id: string
  title: string
  enforcement_mode: string
  owner_team: string | null
}

type Response = { items: Row[]; total: number }

export function ContractsPage() {
  const q = useQuery({
    queryKey: ['contracts'],
    queryFn: () => apiGet<Response>('/api/v1/contracts'),
  })

  if (q.isLoading) {
    return <p className="text-[var(--color-ink-muted)]">Loading contracts…</p>
  }
  if (q.error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        {String(q.error)}
      </div>
    )
  }

  const rows = q.data?.items ?? []

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className={PAGE_TITLE}>Contracts</h1>
          <p className="mt-2 text-[var(--color-ink-muted)]">
            {q.data?.total ?? 0} contract(s) in the catalog.
          </p>
        </div>
        <Link
          to="/contracts/new"
          className="rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 dark:bg-teal-500 dark:hover:bg-teal-600"
        >
          New contract
        </Link>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No contracts yet"
          body="Create one with full YAML control—no separate wizard."
          action={
            <Link
              to="/contracts/new"
              className="mt-4 inline-block rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 dark:bg-teal-500"
            >
              New contract
            </Link>
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-[var(--color-border)] dark:border-zinc-800">
          <table className="w-full min-w-[32rem] text-left text-sm">
            <thead className="border-b border-[var(--color-border)] bg-stone-100/80 dark:border-zinc-800 dark:bg-zinc-900">
              <tr>
                <th className="px-4 py-3 font-medium">ID</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Team</th>
                <th className="px-4 py-3 font-medium">Mode</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)] dark:divide-zinc-800">
              {rows.map((r) => (
                <tr key={r.contract_id} className="bg-[var(--color-surface-elevated)] dark:bg-zinc-900/30">
                  <td className="px-4 py-3 font-mono text-xs">
                    <Link
                      to={`/contracts/${encodeURIComponent(r.contract_id)}`}
                      className="text-teal-700 underline-offset-2 hover:underline dark:text-teal-400"
                    >
                      {r.contract_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/contracts/${encodeURIComponent(r.contract_id)}`}
                      className="text-[var(--color-ink)] hover:text-teal-700 dark:hover:text-teal-400"
                    >
                      {r.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-[var(--color-ink-muted)]">{r.owner_team ?? '—'}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-md bg-stone-200 px-2 py-0.5 text-xs dark:bg-zinc-800">
                      {r.enforcement_mode}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function EmptyState(props: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--color-border)] bg-stone-50/50 px-6 py-12 text-center dark:border-zinc-700 dark:bg-zinc-900/20">
      <p className="font-medium text-[var(--color-ink)]">{props.title}</p>
      <p className="mt-2 text-sm text-[var(--color-ink-muted)]">{props.body}</p>
      {props.action}
    </div>
  )
}
