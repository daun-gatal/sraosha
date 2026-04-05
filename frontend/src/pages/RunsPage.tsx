import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiGet } from '../api/client'
import { PAGE_TITLE, SECTION_TITLE } from '../ui/titleStyles'

type Tab = 'validation' | 'dq'

type ValidationRunRow = {
  id: string
  contract_id: string
  status: string
  run_at: string
  checks_passed: number
  checks_total: number
  checks_failed: number
  duration_ms: number | null
  triggered_by: string | null
}

type ValidationRunDetail = ValidationRunRow & {
  enforcement_mode: string
  failures: Record<string, unknown>[] | null
  server: string | null
  error_message: string | null
  run_log: string | null
}

type DQRunRow = {
  id: string
  dq_check_id: string
  dq_check_name: string
  status: string
  run_at: string
  checks_passed: number
  checks_total: number
  checks_warned: number
  checks_failed: number
  duration_ms: number | null
  triggered_by: string
}

type DQRunDetail = Omit<DQRunRow, 'dq_check_name'> & {
  results_json: Record<string, unknown> | null
  diagnostics_json: Record<string, unknown> | null
  run_log: string | null
}

type ListResponse<T> = { items: T[]; total: number }

type ContractRow = { contract_id: string; title: string }

type Selected =
  | { kind: 'validation'; id: string }
  | { kind: 'dq'; checkId: string; runId: string; checkName: string }
  | null

function statusBadgeClass(status: string): string {
  const s = status.toLowerCase()
  if (s === 'passed' || s === 'healthy')
    return 'bg-teal-100 text-teal-900 dark:bg-teal-950/60 dark:text-teal-300'
  if (s === 'failed' || s === 'error')
    return 'bg-red-100 text-red-900 dark:bg-red-950/50 dark:text-red-200'
  if (s === 'warning' || s === 'warned')
    return 'bg-amber-100 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200'
  return 'bg-stone-200 text-stone-800 dark:bg-zinc-800 dark:text-zinc-200'
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  if (value == null) return null
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  return (
    <div className="space-y-1">
      <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-ink-muted)]">
        {label}
      </div>
      <pre className="max-h-48 overflow-auto rounded-lg border border-[var(--color-border)] bg-stone-50 p-3 text-xs leading-relaxed dark:border-zinc-800 dark:bg-zinc-950/80">
        {text}
      </pre>
    </div>
  )
}

export function RunsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [tab, setTab] = useState<Tab>('validation')
  const [selected, setSelected] = useState<Selected>(null)

  useEffect(() => {
    const runId = searchParams.get('runId')
    if (!runId) return

    const tabParam = searchParams.get('tab')

    // Defer state updates so we do not set state synchronously in the effect body (eslint react-hooks/set-state-in-effect).
    const t = window.setTimeout(() => {
      if (tabParam === 'dq') {
        const checkId = searchParams.get('checkId')
        if (!checkId) {
          setSearchParams({}, { replace: true })
          return
        }
        const checkName = searchParams.get('checkName') ?? ''
        setTab('dq')
        setSelected({
          kind: 'dq',
          checkId,
          runId,
          checkName: checkName || 'Check',
        })
        setSearchParams({}, { replace: true })
        return
      }

      if (tabParam === 'validation' || tabParam === null) {
        setTab('validation')
        setSelected({ kind: 'validation', id: runId })
        setSearchParams({}, { replace: true })
        return
      }

      setSearchParams({}, { replace: true })
    }, 0)

    return () => window.clearTimeout(t)
  }, [searchParams, setSearchParams])

  const contractsQ = useQuery({
    queryKey: ['contracts'],
    queryFn: () => apiGet<ListResponse<ContractRow>>('/api/v1/contracts'),
  })

  const titleByContractId = useMemo(() => {
    const m = new Map<string, string>()
    for (const c of contractsQ.data?.items ?? []) {
      m.set(c.contract_id, c.title)
    }
    return m
  }, [contractsQ.data?.items])

  const validationQ = useQuery({
    queryKey: ['runs', 'list'],
    queryFn: () => apiGet<ListResponse<ValidationRunRow>>('/api/v1/runs?limit=50'),
  })

  const dqQ = useQuery({
    queryKey: ['runs', 'dq-list'],
    queryFn: () => apiGet<ListResponse<DQRunRow>>('/api/v1/runs/dq?limit=50'),
  })

  const valDetailQ = useQuery({
    queryKey: ['runs', 'validation-detail', selected?.kind === 'validation' ? selected.id : null],
    queryFn: () =>
      apiGet<ValidationRunDetail>(`/api/v1/runs/${(selected as { kind: 'validation'; id: string }).id}`),
    enabled: selected?.kind === 'validation',
  })

  const dqDetailQ = useQuery({
    queryKey: [
      'runs',
      'dq-detail',
      selected?.kind === 'dq' ? selected.checkId : null,
      selected?.kind === 'dq' ? selected.runId : null,
      selected?.kind === 'dq' ? selected.checkName : null,
    ],
    queryFn: () => {
      const s = selected as { kind: 'dq'; checkId: string; runId: string; checkName: string }
      return apiGet<DQRunDetail>(`/api/v1/data-quality/${s.checkId}/runs/${s.runId}`)
    },
    enabled: selected?.kind === 'dq',
  })

  const closeDrawer = useCallback(() => setSelected(null), [])

  useEffect(() => {
    if (!selected) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeDrawer()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selected, closeDrawer])

  const loading =
    tab === 'validation' ? validationQ.isLoading : dqQ.isLoading
  const err = tab === 'validation' ? validationQ.error : dqQ.error
  const rowsVal = validationQ.data?.items ?? []
  const rowsDq = dqQ.data?.items ?? []

  return (
    <div className="space-y-8">
      <div>
        <h1 className={PAGE_TITLE}>
          Runs
        </h1>
        <p className="mt-2 max-w-2xl text-[var(--color-ink-muted)]">
          Contract validation executes your YAML checks against the database. Data Quality runs
          execute Soda checks. Select a row to inspect logs, timings, and structured results.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] p-1 dark:border-zinc-800 dark:bg-zinc-900/40">
        {(
          [
            ['validation', 'Contract Validation'],
            ['dq', 'Data Quality'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => {
              setTab(id)
              setSelected(null)
            }}
            className={[
              'rounded-xl px-4 py-2 text-sm font-medium transition-colors',
              tab === id
                ? 'bg-teal-600 text-white shadow-sm dark:bg-teal-500'
                : 'text-[var(--color-ink-muted)] hover:bg-stone-200/80 dark:hover:bg-zinc-800',
            ].join(' ')}
          >
            {label}
          </button>
        ))}
      </div>

      {contractsQ.isLoading && (
        <p className="text-sm text-[var(--color-ink-muted)]">Loading contract names…</p>
      )}

      {loading && <p className="text-[var(--color-ink-muted)]">Loading runs…</p>}
      {err && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {String(err)}
        </div>
      )}

      {!loading && !err && tab === 'validation' && (
        <>
          {rowsVal.length === 0 ? (
            <p className="text-[var(--color-ink-muted)]">No validation runs yet.</p>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-[var(--color-border)] dark:border-zinc-800">
              <table className="w-full min-w-[36rem] text-left text-sm">
                <thead className="border-b border-[var(--color-border)] bg-stone-100/80 dark:border-zinc-800 dark:bg-zinc-900">
                  <tr>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Contract</th>
                    <th className="px-4 py-3 font-medium">Checks</th>
                    <th className="px-4 py-3 font-medium">When</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)] dark:divide-zinc-800">
                  {rowsVal.map((r) => {
                    const title = titleByContractId.get(r.contract_id) ?? r.contract_id
                    return (
                      <tr
                        key={r.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => setSelected({ kind: 'validation', id: r.id })}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ')
                            setSelected({ kind: 'validation', id: r.id })
                        }}
                        className="cursor-pointer bg-[var(--color-surface-elevated)] transition-colors hover:bg-teal-50/50 dark:bg-zinc-900/30 dark:hover:bg-teal-950/20"
                      >
                        <td className="px-4 py-3">
                          <span
                            className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${statusBadgeClass(r.status)}`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-medium text-[var(--color-ink)]">{title}</div>
                          <div className="font-mono text-xs text-[var(--color-ink-muted)]">
                            {r.contract_id}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-[var(--color-ink-muted)]">
                          {r.checks_passed}/{r.checks_total}
                          {r.checks_failed > 0 && (
                            <span className="ml-1 text-amber-700 dark:text-amber-400">
                              ({r.checks_failed} failed)
                            </span>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-[var(--color-ink-muted)]">
                          {new Date(r.run_at).toLocaleString()}
                          {r.duration_ms != null && (
                            <span className="ml-2 text-xs opacity-80">{r.duration_ms} ms</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {!loading && !err && tab === 'dq' && (
        <>
          {rowsDq.length === 0 ? (
            <p className="text-[var(--color-ink-muted)]">No data quality runs yet.</p>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-[var(--color-border)] dark:border-zinc-800">
              <table className="w-full min-w-[36rem] text-left text-sm">
                <thead className="border-b border-[var(--color-border)] bg-stone-100/80 dark:border-zinc-800 dark:bg-zinc-900">
                  <tr>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Check</th>
                    <th className="px-4 py-3 font-medium">Checks</th>
                    <th className="px-4 py-3 font-medium">When</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)] dark:divide-zinc-800">
                  {rowsDq.map((r) => (
                    <tr
                      key={r.id}
                      role="button"
                      tabIndex={0}
                      onClick={() =>
                        setSelected({
                          kind: 'dq',
                          checkId: r.dq_check_id,
                          runId: r.id,
                          checkName: r.dq_check_name,
                        })
                      }
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ')
                          setSelected({
                            kind: 'dq',
                            checkId: r.dq_check_id,
                            runId: r.id,
                            checkName: r.dq_check_name,
                          })
                      }}
                      className="cursor-pointer bg-[var(--color-surface-elevated)] transition-colors hover:bg-teal-50/50 dark:bg-zinc-900/30 dark:hover:bg-teal-950/20"
                    >
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${statusBadgeClass(r.status)}`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-[var(--color-ink)]">{r.dq_check_name}</div>
                        <div className="font-mono text-xs text-[var(--color-ink-muted)]">
                          {r.dq_check_id}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-[var(--color-ink-muted)]">
                        {r.checks_passed}/{r.checks_total}
                        {r.checks_warned > 0 && (
                          <span className="ml-1 text-amber-700 dark:text-amber-400">
                            ({r.checks_warned} warn)
                          </span>
                        )}
                        {r.checks_failed > 0 && (
                          <span className="ml-1 text-red-700 dark:text-red-400">
                            ({r.checks_failed} fail)
                          </span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-[var(--color-ink-muted)]">
                        {new Date(r.run_at).toLocaleString()}
                        {r.duration_ms != null && (
                          <span className="ml-2 text-xs opacity-80">{r.duration_ms} ms</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {selected && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <button
            type="button"
            className="absolute inset-0 bg-black/40 backdrop-blur-[1px]"
            aria-label="Close"
            onClick={closeDrawer}
          />
          <div className="relative flex h-full w-full max-w-lg flex-col border-l border-[var(--color-border)] bg-[var(--color-surface-elevated)] shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-4 dark:border-zinc-800">
              <div>
                <h2 className={SECTION_TITLE}>
                  Run Details
                </h2>
                <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                  {selected.kind === 'validation' ? 'Contract Validation' : 'Data Quality Scan'}
                </p>
              </div>
              <button
                type="button"
                onClick={closeDrawer}
                className="rounded-full px-3 py-1 text-sm text-[var(--color-ink-muted)] hover:bg-stone-200 dark:hover:bg-zinc-800"
              >
                Close
              </button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
              {selected.kind === 'validation' && valDetailQ.isLoading && (
                <p className="text-sm text-[var(--color-ink-muted)]">Loading…</p>
              )}
              {selected.kind === 'validation' && valDetailQ.error && (
                <p className="text-sm text-red-700 dark:text-red-300">{String(valDetailQ.error)}</p>
              )}
              {selected.kind === 'validation' && valDetailQ.data && (
                <ValidationDetailBody data={valDetailQ.data} titleByContractId={titleByContractId} />
              )}

              {selected.kind === 'dq' && dqDetailQ.isLoading && (
                <p className="text-sm text-[var(--color-ink-muted)]">Loading…</p>
              )}
              {selected.kind === 'dq' && dqDetailQ.error && (
                <p className="text-sm text-red-700 dark:text-red-300">{String(dqDetailQ.error)}</p>
              )}
              {selected.kind === 'dq' && dqDetailQ.data && (
                <DQDetailBody data={dqDetailQ.data} checkName={selected.checkName} />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ValidationDetailBody({
  data,
  titleByContractId,
}: {
  data: ValidationRunDetail
  titleByContractId: Map<string, string>
}) {
  const title = titleByContractId.get(data.contract_id) ?? data.contract_id
  return (
    <>
      <dl className="grid grid-cols-1 gap-3 text-sm">
        <div>
          <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Contract</dt>
          <dd className="mt-0.5 font-medium">{title}</dd>
          <dd className="font-mono text-xs text-[var(--color-ink-muted)]">{data.contract_id}</dd>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Status</dt>
            <dd className="mt-0.5 capitalize">{data.status}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Enforcement</dt>
            <dd className="mt-0.5">{data.enforcement_mode}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Checks</dt>
            <dd className="mt-0.5">
              {data.checks_passed}/{data.checks_total} passed
              {data.checks_failed > 0 && ` · ${data.checks_failed} failed`}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Duration</dt>
            <dd className="mt-0.5">{data.duration_ms != null ? `${data.duration_ms} ms` : '—'}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Triggered By</dt>
            <dd className="mt-0.5">{data.triggered_by ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Run At</dt>
            <dd className="mt-0.5">{new Date(data.run_at).toLocaleString()}</dd>
          </div>
          {data.server && (
            <div className="col-span-2">
              <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Server</dt>
              <dd className="mt-0.5 font-mono text-xs">{data.server}</dd>
            </div>
          )}
        </div>
      </dl>

      {data.error_message && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {data.error_message}
        </div>
      )}

      <Link
        to={`/contracts/${encodeURIComponent(data.contract_id)}`}
        className="inline-flex text-sm font-medium text-teal-700 underline-offset-2 hover:underline dark:text-teal-400"
      >
        Open Contract
      </Link>

      <div className="space-y-1">
        <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-ink-muted)]">
          Log
        </div>
        {data.run_log ? (
          <pre className="max-h-72 overflow-auto rounded-lg border border-[var(--color-border)] bg-stone-50 p-3 text-xs leading-relaxed dark:border-zinc-800 dark:bg-zinc-950/80">
            {data.run_log}
          </pre>
        ) : (
          <p className="text-sm text-[var(--color-ink-muted)]">No engine log captured for this run.</p>
        )}
      </div>

      {data.failures && data.failures.length > 0 && (
        <JsonBlock label="Failures" value={data.failures} />
      )}
    </>
  )
}

function DQDetailBody({ data, checkName }: { data: DQRunDetail; checkName: string }) {
  return (
    <>
      <dl className="grid grid-cols-1 gap-3 text-sm">
        <div>
          <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Check</dt>
          <dd className="mt-0.5 font-medium">{checkName}</dd>
          <dd className="font-mono text-xs text-[var(--color-ink-muted)]">{data.dq_check_id}</dd>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Status</dt>
            <dd className="mt-0.5 capitalize">{data.status}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Triggered By</dt>
            <dd className="mt-0.5">{data.triggered_by}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Checks</dt>
            <dd className="mt-0.5">
              {data.checks_passed}/{data.checks_total} ok
              {data.checks_warned > 0 && ` · ${data.checks_warned} warn`}
              {data.checks_failed > 0 && ` · ${data.checks_failed} fail`}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Duration</dt>
            <dd className="mt-0.5">{data.duration_ms != null ? `${data.duration_ms} ms` : '—'}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-xs uppercase text-[var(--color-ink-muted)]">Run At</dt>
            <dd className="mt-0.5">{new Date(data.run_at).toLocaleString()}</dd>
          </div>
        </div>
      </dl>

      <Link
        to={`/data-quality/${encodeURIComponent(data.dq_check_id)}`}
        className="inline-flex text-sm font-medium text-teal-700 underline-offset-2 hover:underline dark:text-teal-400"
      >
        Open Check
      </Link>

      <JsonBlock label="Results" value={data.results_json} />
      <JsonBlock label="Diagnostics" value={data.diagnostics_json} />

      {data.run_log && (
        <div className="space-y-1">
          <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-ink-muted)]">
            Log
          </div>
          <pre className="max-h-72 overflow-auto rounded-lg border border-[var(--color-border)] bg-stone-50 p-3 text-xs leading-relaxed dark:border-zinc-800 dark:bg-zinc-950/80">
            {data.run_log}
          </pre>
        </div>
      )}
    </>
  )
}
