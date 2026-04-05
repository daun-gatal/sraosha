import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent, KeyboardEvent, MouseEvent } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPost } from '../api/client'
import { PAGE_TITLE, SECTION_TITLE } from '../ui/titleStyles'

type ScheduleListItem = {
  id: string
  schedule_type: 'contract' | 'data_quality'
  contract_id: string | null
  contract_title: string | null
  dq_check_id: string | null
  dq_check_name: string | null
  owner_team: string | null
  is_enabled: boolean
  interval_preset: string
  cron_expression: string | null
  next_run_at: string
  last_run_at: string | null
  last_run_id: string | null
}

type SchedulesResponse = { items: ScheduleListItem[]; total: number }

type ContractOption = { contract_id: string; title: string }
type DQOption = { id: string; name: string }

type ScheduleRequestBody = {
  interval_preset: string
  cron_expression: string | null
  is_enabled: boolean
}

const PRESETS: { value: string; label: string }[] = [
  { value: 'hourly', label: 'Hourly' },
  { value: 'every_6h', label: 'Every 6 Hours' },
  { value: 'every_12h', label: 'Every 12 Hours' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'custom', label: 'Custom (Cron)' },
]

function formatPreset(preset: string, cron: string | null): string {
  const p = PRESETS.find((x) => x.value === preset)
  if (preset === 'custom' && cron) return `Custom: ${cron}`
  return p?.label ?? preset
}

function runsLastRunHref(s: ScheduleListItem): string {
  const p = new URLSearchParams()
  p.set('runId', s.last_run_id!)
  if (s.schedule_type === 'contract') {
    p.set('tab', 'validation')
  } else {
    p.set('tab', 'dq')
    if (s.dq_check_id) p.set('checkId', s.dq_check_id)
    if (s.dq_check_name) p.set('checkName', s.dq_check_name)
  }
  return `/runs?${p.toString()}`
}

type ModalState =
  | { open: false }
  | {
      open: true
      mode: 'create'
      resource: 'contract' | 'data_quality'
      preselectContractId?: string
      preselectDqCheckId?: string
    }
  | {
      open: true
      mode: 'edit'
      item: ScheduleListItem
    }

export function SchedulesPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [sectionTab, setSectionTab] = useState<'contract' | 'data_quality'>('contract')
  const [modal, setModal] = useState<ModalState>({ open: false })
  const [deleteTarget, setDeleteTarget] = useState<ScheduleListItem | null>(null)

  useEffect(() => {
    const focus = searchParams.get('focus')
    const contractId = searchParams.get('contractId')
    const checkId = searchParams.get('checkId')
    if (focus === 'contract' && contractId) {
      const t = window.setTimeout(() => {
        setSectionTab('contract')
        setModal({
          open: true,
          mode: 'create',
          resource: 'contract',
          preselectContractId: contractId,
        })
        setSearchParams({}, { replace: true })
      }, 0)
      return () => window.clearTimeout(t)
    }
    if (focus === 'dq' && checkId) {
      const t = window.setTimeout(() => {
        setSectionTab('data_quality')
        setModal({
          open: true,
          mode: 'create',
          resource: 'data_quality',
          preselectDqCheckId: checkId,
        })
        setSearchParams({}, { replace: true })
      }, 0)
      return () => window.clearTimeout(t)
    }
  }, [searchParams, setSearchParams])

  const schedulesQ = useQuery({
    queryKey: ['schedules', 'all'],
    queryFn: () => apiGet<SchedulesResponse>('/api/v1/schedules?type=all'),
  })

  const contractsQ = useQuery({
    queryKey: ['contracts'],
    queryFn: () => apiGet<{ items: ContractOption[] }>('/api/v1/contracts'),
  })

  const dqQ = useQuery({
    queryKey: ['data-quality', 'list'],
    queryFn: () => apiGet<{ items: DQOption[] }>('/api/v1/data-quality'),
  })

  const contractRows = useMemo(
    () => schedulesQ.data?.items.filter((s) => s.schedule_type === 'contract') ?? [],
    [schedulesQ.data?.items],
  )
  const dqRows = useMemo(
    () => schedulesQ.data?.items.filter((s) => s.schedule_type === 'data_quality') ?? [],
    [schedulesQ.data?.items],
  )

  const saveMutation = useMutation({
    mutationFn: async (args: {
      body: ScheduleRequestBody
      contractId?: string
      dqCheckId?: string
    }) => {
      const { body, contractId, dqCheckId } = args
      if (contractId) {
        return apiPost(`/api/v1/schedules/contracts/${encodeURIComponent(contractId)}/schedule`, body)
      }
      if (dqCheckId) {
        return apiPost(`/api/v1/schedules/dq/${dqCheckId}/schedule`, body)
      }
      throw new Error('Missing target')
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schedules'] })
      setModal({ open: false })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (item: ScheduleListItem) => {
      if (item.schedule_type === 'contract' && item.contract_id) {
        await apiDelete(
          `/api/v1/schedules/contracts/${encodeURIComponent(item.contract_id)}/schedule`,
        )
        return
      }
      if (item.schedule_type === 'data_quality' && item.dq_check_id) {
        await apiDelete(`/api/v1/schedules/dq/${item.dq_check_id}/schedule`)
        return
      }
      throw new Error('Invalid schedule row')
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schedules'] })
      setDeleteTarget(null)
    },
  })

  if (schedulesQ.isLoading) {
    return <p className="text-[var(--color-ink-muted)]">Loading schedules…</p>
  }
  if (schedulesQ.error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        {String(schedulesQ.error)}
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className={PAGE_TITLE}>
            Schedules
          </h1>
          <p className="mt-2 max-w-2xl text-[var(--color-ink-muted)]">
            Automate contract validation and data quality scans on a fixed interval or cron. Times
            shown are computed next runs (Celery beat executes them when due).
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModal({ open: true, mode: 'create', resource: 'contract' })}
          className="rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 dark:bg-teal-500 dark:hover:bg-teal-600"
        >
          Add Schedule
        </button>
      </div>

      <div className="flex flex-wrap gap-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] p-1 dark:border-zinc-800 dark:bg-zinc-900/40">
        {(
          [
            ['contract', 'Contract Validation', contractRows.length],
            ['data_quality', 'Data Quality', dqRows.length],
          ] as const
        ).map(([id, label, count]) => (
          <button
            key={id}
            type="button"
            onClick={() => setSectionTab(id)}
            className={[
              'rounded-xl px-4 py-2 text-sm font-medium transition-colors',
              sectionTab === id
                ? 'bg-teal-600 text-white shadow-sm dark:bg-teal-500'
                : 'text-[var(--color-ink-muted)] hover:bg-stone-200/80 dark:hover:bg-zinc-800',
            ].join(' ')}
          >
            {label}
            <span className="ml-1.5 tabular-nums opacity-80">({count})</span>
          </button>
        ))}
      </div>

      {sectionTab === 'contract' && (
        <ScheduleTable
          rows={contractRows}
          emptyTitle="No Contract Schedules"
          emptyBody="Add a schedule to validate YAML contracts on a recurring basis."
          resourceLabel="contract"
          onEdit={(item) => setModal({ open: true, mode: 'edit', item })}
          onDelete={(item) => setDeleteTarget(item)}
        />
      )}
      {sectionTab === 'data_quality' && (
        <ScheduleTable
          rows={dqRows}
          emptyTitle="No Data Quality Schedules"
          emptyBody="Add a schedule to run Soda checks automatically."
          resourceLabel="check"
          onEdit={(item) => setModal({ open: true, mode: 'edit', item })}
          onDelete={(item) => setDeleteTarget(item)}
        />
      )}

      {modal.open && (
        <ScheduleModal
          modal={modal}
          onClose={() => setModal({ open: false })}
          contracts={contractsQ.data?.items ?? []}
          dqChecks={dqQ.data?.items ?? []}
          contractsLoading={contractsQ.isLoading}
          dqLoading={dqQ.isLoading}
          onSubmit={(body, target) => saveMutation.mutate({ body, ...target })}
          submitting={saveMutation.isPending}
          error={saveMutation.error ? String(saveMutation.error) : null}
        />
      )}

      {deleteTarget && (
        <ConfirmDelete
          item={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => deleteMutation.mutate(deleteTarget)}
          busy={deleteMutation.isPending}
          error={deleteMutation.error ? String(deleteMutation.error) : null}
        />
      )}
    </div>
  )
}

function ScheduleTable({
  rows,
  emptyTitle,
  emptyBody,
  resourceLabel,
  onEdit,
  onDelete,
}: {
  rows: ScheduleListItem[]
  emptyTitle: string
  emptyBody: string
  resourceLabel: string
  onEdit: (item: ScheduleListItem) => void
  onDelete: (item: ScheduleListItem) => void
}) {
  if (rows.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-6 py-12 text-center dark:border-zinc-800">
        <h2 className={SECTION_TITLE}>{emptyTitle}</h2>
        <p className="mt-2 text-sm text-[var(--color-ink-muted)]">{emptyBody}</p>
        <p className="mt-4 text-xs text-[var(--color-ink-muted)]">
          Create a {resourceLabel} first if nothing appears in the add dialog.
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-[var(--color-border)] dark:border-zinc-800">
      <table className="w-full min-w-[40rem] text-left text-sm">
        <thead className="border-b border-[var(--color-border)] bg-stone-100/80 dark:border-zinc-800 dark:bg-zinc-900">
          <tr>
            <th className="px-4 py-3 font-medium">Resource</th>
            <th className="px-4 py-3 font-medium">Interval</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Next Run</th>
            <th className="px-4 py-3 font-medium">Last Run</th>
            <th className="px-4 py-3 font-medium text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--color-border)] dark:divide-zinc-800">
          {rows.map((s) => {
            const title =
              s.schedule_type === 'contract'
                ? (s.contract_title ?? s.contract_id ?? '—')
                : (s.dq_check_name ?? s.dq_check_id ?? '—')
            const sub =
              s.schedule_type === 'contract'
                ? s.owner_team
                  ? `Team: ${s.owner_team}`
                  : s.contract_id
                : s.dq_check_id
            return (
              <tr key={s.id} className="bg-[var(--color-surface-elevated)] dark:bg-zinc-900/30">
                <td className="px-4 py-3">
                  <div className="font-medium text-[var(--color-ink)]">{title}</div>
                  {sub && (
                    <div className="mt-0.5 font-mono text-xs text-[var(--color-ink-muted)]">{sub}</div>
                  )}
                </td>
                <td className="px-4 py-3 text-[var(--color-ink-muted)]">
                  {formatPreset(s.interval_preset, s.cron_expression)}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={
                      s.is_enabled
                        ? 'rounded-full bg-teal-100 px-2 py-0.5 text-xs font-medium text-teal-900 dark:bg-teal-950/60 dark:text-teal-300'
                        : 'rounded-full bg-stone-200 px-2 py-0.5 text-xs font-medium text-stone-700 dark:bg-zinc-800 dark:text-zinc-300'
                    }
                  >
                    {s.is_enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--color-ink-muted)]">
                  {new Date(s.next_run_at).toLocaleString()}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--color-ink-muted)]">
                  {s.last_run_at ? (
                    s.last_run_id ? (
                      <Link
                        className="text-teal-700 underline underline-offset-2 hover:text-teal-800 dark:text-teal-400 dark:hover:text-teal-300"
                        to={runsLastRunHref(s)}
                      >
                        {new Date(s.last_run_at).toLocaleString()}
                      </Link>
                    ) : (
                      new Date(s.last_run_at).toLocaleString()
                    )
                  ) : (
                    '—'
                  )}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onEdit(s)}
                    className="mr-2 text-sm font-medium text-teal-700 hover:underline dark:text-teal-400"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(s)}
                    className="text-sm font-medium text-red-700 hover:underline dark:text-red-400"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ScheduleModal({
  modal,
  onClose,
  contracts,
  dqChecks,
  contractsLoading,
  dqLoading,
  onSubmit,
  submitting,
  error,
}: {
  modal: Extract<ModalState, { open: true }>
  onClose: () => void
  contracts: ContractOption[]
  dqChecks: DQOption[]
  contractsLoading: boolean
  dqLoading: boolean
  onSubmit: (body: ScheduleRequestBody, target: { contractId?: string; dqCheckId?: string }) => void
  submitting: boolean
  error: string | null
}) {
  const isEdit = modal.mode === 'edit'
  const initial = isEdit ? modal.item : null
  const create = !isEdit && modal.mode === 'create' ? modal : null

  const [resource, setResource] = useState<'contract' | 'data_quality'>(() => {
    if (isEdit) return initial!.schedule_type
    if (create?.preselectContractId) return 'contract'
    if (create?.preselectDqCheckId) return 'data_quality'
    return create!.resource
  })
  const [contractId, setContractId] = useState(() => {
    if (isEdit && initial!.schedule_type === 'contract') return initial!.contract_id ?? ''
    if (create?.preselectContractId) return create.preselectContractId
    return ''
  })
  const [dqCheckId, setDqCheckId] = useState(() => {
    if (isEdit && initial!.schedule_type === 'data_quality') return initial!.dq_check_id ?? ''
    if (create?.preselectDqCheckId) return create.preselectDqCheckId
    return ''
  })
  const [intervalPreset, setIntervalPreset] = useState(
    () => initial?.interval_preset ?? 'daily',
  )
  const [cronExpression, setCronExpression] = useState(
    () => initial?.cron_expression ?? '',
  )
  const [isEnabled, setIsEnabled] = useState(() => initial?.is_enabled ?? true)

  const body: ScheduleRequestBody = {
    interval_preset: intervalPreset,
    cron_expression: intervalPreset === 'custom' ? cronExpression || null : null,
    is_enabled: isEnabled,
  }

  const canSubmit = () => {
    if (intervalPreset === 'custom' && !(cronExpression || '').trim()) return false
    if (!isEdit) {
      if (resource === 'contract' && !contractId) return false
      if (resource === 'data_quality' && !dqCheckId) return false
    }
    return true
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit()) return
    if (isEdit && initial) {
      if (initial.schedule_type === 'contract' && initial.contract_id) {
        onSubmit(body, { contractId: initial.contract_id })
      } else if (initial.schedule_type === 'data_quality' && initial.dq_check_id) {
        onSubmit(body, { dqCheckId: initial.dq_check_id })
      }
      return
    }
    if (resource === 'contract') onSubmit(body, { contractId })
    else onSubmit(body, { dqCheckId })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 py-12">
      <div
        className="absolute inset-0"
        role="presentation"
        onClick={onClose}
        onKeyDown={(e) => e.key === 'Escape' && onClose()}
        tabIndex={-1}
      />
      <div className="relative w-full max-w-lg rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="border-b border-[var(--color-border)] px-5 py-4 dark:border-zinc-800">
          <h2 className={SECTION_TITLE}>
            {isEdit ? 'Edit Schedule' : 'Add Schedule'}
          </h2>
          <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
            {isEdit
              ? 'Update timing and whether this schedule is active.'
              : 'Choose what to run and how often.'}
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-4">
          {!isEdit && (
            <>
              <div>
                <span className="text-xs font-medium uppercase text-[var(--color-ink-muted)]">
                  Resource Type
                </span>
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    onClick={() => setResource('contract')}
                    className={`rounded-xl px-3 py-2 text-sm font-medium ${
                      resource === 'contract'
                        ? 'bg-teal-600 text-white dark:bg-teal-500'
                        : 'border border-[var(--color-border)] dark:border-zinc-700'
                    }`}
                  >
                    Contract Validation
                  </button>
                  <button
                    type="button"
                    onClick={() => setResource('data_quality')}
                    className={`rounded-xl px-3 py-2 text-sm font-medium ${
                      resource === 'data_quality'
                        ? 'bg-teal-600 text-white dark:bg-teal-500'
                        : 'border border-[var(--color-border)] dark:border-zinc-700'
                    }`}
                  >
                    Data Quality
                  </button>
                </div>
              </div>
              {resource === 'contract' && (
                <label className="block">
                  <span className="text-xs font-medium uppercase text-[var(--color-ink-muted)]">
                    Contract
                  </span>
                  <select
                    required
                    value={contractId}
                    onChange={(e) => setContractId(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-3 py-2 text-sm dark:border-zinc-700"
                    disabled={contractsLoading}
                  >
                    <option value="">{contractsLoading ? 'Loading…' : 'Select Contract'}</option>
                    {contracts.map((c) => (
                      <option key={c.contract_id} value={c.contract_id}>
                        {c.title} ({c.contract_id})
                      </option>
                    ))}
                  </select>
                  {contracts.length === 0 && !contractsLoading && (
                    <p className="mt-2 text-xs text-amber-800 dark:text-amber-300">
                      No contracts yet.{' '}
                      <Link className="underline" to="/contracts/new">
                        Create one
                      </Link>
                    </p>
                  )}
                </label>
              )}
              {resource === 'data_quality' && (
                <label className="block">
                  <span className="text-xs font-medium uppercase text-[var(--color-ink-muted)]">
                    DQ Check
                  </span>
                  <select
                    required
                    value={dqCheckId}
                    onChange={(e) => setDqCheckId(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-3 py-2 text-sm dark:border-zinc-700"
                    disabled={dqLoading}
                  >
                    <option value="">{dqLoading ? 'Loading…' : 'Select Check'}</option>
                    {dqChecks.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                  {dqChecks.length === 0 && !dqLoading && (
                    <p className="mt-2 text-xs text-amber-800 dark:text-amber-300">
                      No checks yet.{' '}
                      <Link className="underline" to="/data-quality/new">
                        Create one
                      </Link>
                    </p>
                  )}
                </label>
              )}
            </>
          )}
          {isEdit && initial && (
            <div className="rounded-xl border border-[var(--color-border)] bg-stone-50 px-3 py-2 text-sm dark:border-zinc-800 dark:bg-zinc-900/50">
              <div className="font-medium text-[var(--color-ink)]">
                {initial.schedule_type === 'contract'
                  ? (initial.contract_title ?? initial.contract_id)
                  : (initial.dq_check_name ?? initial.dq_check_id)}
              </div>
              <div className="mt-1 text-xs text-[var(--color-ink-muted)]">
                {initial.schedule_type === 'contract' ? (
                  <Link
                    className="text-teal-700 underline dark:text-teal-400"
                    to={`/contracts/${encodeURIComponent(initial.contract_id ?? '')}`}
                  >
                    Open Contract
                  </Link>
                ) : (
                  <Link
                    className="text-teal-700 underline dark:text-teal-400"
                    to={`/data-quality/${encodeURIComponent(initial.dq_check_id ?? '')}`}
                  >
                    Open Check
                  </Link>
                )}
              </div>
            </div>
          )}

          <label className="block">
            <span className="text-xs font-medium uppercase text-[var(--color-ink-muted)]">
              Interval
            </span>
            <select
              value={intervalPreset}
              onChange={(e) => setIntervalPreset(e.target.value)}
              className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-3 py-2 text-sm dark:border-zinc-700"
            >
              {PRESETS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>

          {intervalPreset === 'custom' && (
            <label className="block">
              <span className="text-xs font-medium uppercase text-[var(--color-ink-muted)]">
                Cron Expression
              </span>
              <input
                type="text"
                value={cronExpression}
                onChange={(e) => setCronExpression(e.target.value)}
                placeholder="0 * * * *"
                className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-3 py-2 font-mono text-sm dark:border-zinc-700"
              />
              <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                Standard five-field cron (minute hour day month weekday), UTC.
              </p>
            </label>
          )}

          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={isEnabled}
              onChange={(e) => setIsEnabled(e.target.checked)}
              className="rounded border-[var(--color-border)]"
            />
            <span className="text-sm">Enabled</span>
          </label>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 border-t border-[var(--color-border)] pt-4 dark:border-zinc-800">
            <button
              type="button"
              onClick={onClose}
              className="rounded-full px-4 py-2 text-sm font-medium text-[var(--color-ink-muted)] hover:bg-stone-200 dark:hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !canSubmit()}
              className="rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50 dark:bg-teal-500"
            >
              {submitting ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function ConfirmDelete({
  item,
  onCancel,
  onConfirm,
  busy,
  error,
}: {
  item: ScheduleListItem
  onCancel: () => void
  onConfirm: () => void
  busy: boolean
  error: string | null
}) {
  const title =
    item.schedule_type === 'contract'
      ? (item.contract_title ?? item.contract_id)
      : (item.dq_check_name ?? item.dq_check_id)
  const onBackdrop = useCallback(
    (e: MouseEvent) => {
      if (e.target === e.currentTarget) onCancel()
    },
    [onCancel],
  )

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"
      role="presentation"
      onClick={onBackdrop}
      onKeyDown={(e: KeyboardEvent) => e.key === 'Escape' && onCancel()}
    >
      <div className="w-full max-w-md rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] p-5 shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className={SECTION_TITLE}>
          Remove schedule?
        </h3>
        <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
          Stops automated runs for <span className="font-medium text-[var(--color-ink)]">{title}</span>.
          You can add a new schedule later.
        </p>
        {error && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full px-4 py-2 text-sm font-medium text-[var(--color-ink-muted)] hover:bg-stone-200 dark:hover:bg-zinc-800"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="rounded-full bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {busy ? 'Removing…' : 'Remove'}
          </button>
        </div>
      </div>
    </div>
  )
}
