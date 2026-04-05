import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiDelete, apiGet, apiPatch, apiPost } from '../../api/client'
import { CONNECTION_SERVER_TYPES, serverTypeLabel } from './serverTypes'
import { CARD_TITLE, SECTION_TITLE } from '../../ui/titleStyles'

type ConnectionRow = {
  id: string
  name: string
  server_type: string
  description: string | null
  host: string | null
  port: number | null
  database: string | null
  schema_name: string | null
  account: string | null
  warehouse: string | null
  role: string | null
  catalog: string | null
  http_path: string | null
  project: string | null
  dataset: string | null
  location: string | null
  path: string | null
  username: string | null
  extra_params: Record<string, unknown> | null
  has_password: boolean
  has_token: boolean
  has_service_account_json: boolean
  created_at: string
  updated_at: string
}

type FormState = {
  name: string
  description: string
  server_type: string
  host: string
  port: string
  database: string
  schema_name: string
  username: string
  password: string
  account: string
  warehouse: string
  role: string
  catalog: string
  http_path: string
  project: string
  dataset: string
  location: string
  path: string
  token: string
  service_account_json: string
  extra_params_json: string
}

function emptyForm(): FormState {
  return {
    name: '',
    description: '',
    server_type: CONNECTION_SERVER_TYPES[0] ?? 'postgres',
    host: '',
    port: '',
    database: '',
    schema_name: '',
    username: '',
    password: '',
    account: '',
    warehouse: '',
    role: '',
    catalog: '',
    http_path: '',
    project: '',
    dataset: '',
    location: '',
    path: '',
    token: '',
    service_account_json: '',
    extra_params_json: '',
  }
}

function rowToForm(c: ConnectionRow): FormState {
  let extraJson = ''
  if (c.extra_params && Object.keys(c.extra_params).length > 0) {
    try {
      extraJson = JSON.stringify(c.extra_params, null, 2)
    } catch {
      extraJson = ''
    }
  }
  return {
    name: c.name,
    description: c.description ?? '',
    server_type: c.server_type,
    host: c.host ?? '',
    port: c.port != null ? String(c.port) : '',
    database: c.database ?? '',
    schema_name: c.schema_name ?? '',
    username: c.username ?? '',
    password: '',
    account: c.account ?? '',
    warehouse: c.warehouse ?? '',
    role: c.role ?? '',
    catalog: c.catalog ?? '',
    http_path: c.http_path ?? '',
    project: c.project ?? '',
    dataset: c.dataset ?? '',
    location: c.location ?? '',
    path: c.path ?? '',
    token: '',
    service_account_json: '',
    extra_params_json: extraJson,
  }
}

function parsePort(s: string): number | null {
  const t = s.trim()
  if (!t) return null
  const n = parseInt(t, 10)
  return Number.isFinite(n) ? n : null
}

function parseExtraParamsJson(raw: string): Record<string, unknown> | null {
  const t = raw.trim()
  if (!t) return null
  const parsed = JSON.parse(t) as unknown
  if (parsed === null) return null
  if (typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('extra_params must be a JSON object')
  }
  return parsed as Record<string, unknown>
}

function buildTestPayload(
  form: FormState,
  mode: 'create' | 'edit',
  editingId: string | null,
): Record<string, unknown> {
  const body = buildConnectionPayload(form, mode === 'edit' ? 'edit' : 'create')
  if (mode === 'edit' && editingId) {
    body.existing_connection_id = editingId
  }
  return body
}

function buildConnectionPayload(form: FormState, mode: 'create' | 'edit'): Record<string, unknown> {
  const st = form.server_type.trim().toLowerCase()
  let extraParams: Record<string, unknown> | null = null
  if (form.extra_params_json.trim()) {
    extraParams = parseExtraParamsJson(form.extra_params_json)
  }
  const base: Record<string, unknown> = {
    name: form.name.trim(),
    server_type: st,
    description: form.description.trim() || null,
    host: form.host.trim() || null,
    port: parsePort(form.port),
    database: form.database.trim() || null,
    schema_name: form.schema_name.trim() || null,
    account: form.account.trim() || null,
    warehouse: form.warehouse.trim() || null,
    role: form.role.trim() || null,
    catalog: form.catalog.trim() || null,
    http_path: form.http_path.trim() || null,
    project: form.project.trim() || null,
    dataset: form.dataset.trim() || null,
    location: form.location.trim() || null,
    path: form.path.trim() || null,
    username: form.username.trim() || null,
    extra_params: extraParams,
  }
  if (form.password.trim()) base.password = form.password
  if (form.token.trim()) base.token = form.token
  if (form.service_account_json.trim()) base.service_account_json = form.service_account_json
  if (mode === 'edit' && !form.extra_params_json.trim()) {
    base.extra_params = null
  }
  return base
}

type TestResult = { ok: boolean; message: string | null }

export function ConnectionsSettingsPage() {
  const qc = useQueryClient()
  const [mode, setMode] = useState<'idle' | 'create' | 'edit'>('idle')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [testResult, setTestResult] = useState<TestResult | null>(null)

  const listQuery = useQuery({
    queryKey: ['connections'],
    queryFn: () => apiGet<{ items: ConnectionRow[] }>('/api/v1/connections'),
  })

  const items = listQuery.data?.items ?? []

  const openCreate = () => {
    setMode('create')
    setEditingId(null)
    setForm(emptyForm())
    setTestResult(null)
  }

  const openEdit = (c: ConnectionRow) => {
    setMode('edit')
    setEditingId(c.id)
    setForm(rowToForm(c))
    setTestResult(null)
  }

  const cancel = () => {
    setMode('idle')
    setEditingId(null)
    setForm(emptyForm())
    setTestResult(null)
  }

  const createMut = useMutation({
    mutationFn: () => {
      let body: Record<string, unknown>
      try {
        body = buildConnectionPayload(form, 'create')
      } catch (e) {
        return Promise.reject(e instanceof Error ? e : new Error(String(e)))
      }
      if (!body.name || typeof body.name !== 'string' || !body.name.trim()) {
        return Promise.reject(new Error('Name is required'))
      }
      return apiPost<ConnectionRow>('/api/v1/connections', body)
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['connections'] })
      cancel()
    },
  })

  const patchMut = useMutation({
    mutationFn: () => {
      if (!editingId) throw new Error('No connection')
      let body: Record<string, unknown>
      try {
        body = buildConnectionPayload(form, 'edit')
      } catch (e) {
        return Promise.reject(e instanceof Error ? e : new Error(String(e)))
      }
      return apiPatch<ConnectionRow>(`/api/v1/connections/${editingId}`, body)
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['connections'] })
      cancel()
    },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => apiDelete(`/api/v1/connections/${id}`),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['connections'] })
    },
  })

  const testMut = useMutation({
    mutationFn: async () => {
      let body: Record<string, unknown>
      try {
        body = buildTestPayload(form, mode === 'edit' ? 'edit' : 'create', editingId)
      } catch (e) {
        throw e instanceof Error ? e : new Error(String(e))
      }
      return apiPost<TestResult>('/api/v1/connections/test', body)
    },
    onSuccess: (data) => {
      setTestResult({ ok: data.ok, message: data.message ?? null })
    },
    onError: (e: Error) => {
      setTestResult({ ok: false, message: e.message })
    },
  })

  const busy = createMut.isPending || patchMut.isPending || deleteMut.isPending || testMut.isPending
  const err = listQuery.error || createMut.error || patchMut.error || deleteMut.error

  const setF = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((prev) => ({ ...prev, [k]: v }))

  const st = form.server_type.trim().toLowerCase()
  const showSnowflake = st === 'snowflake'
  const showBigQuery = st === 'bigquery'
  const showCatalog = st === 'trino' || st === 'presto'
  const showMotherduck = st === 'motherduck'
  const showMysqlWire = st === 'mysql' || st === 'clickhouse'

  const inputClass =
    'mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950'

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="text-sm text-[var(--color-ink-muted)]">
          Database connections power introspection, contracts, and Soda scans. Secrets are stored encrypted;
          they are never shown again after save.
        </p>
        {mode === 'idle' && (
          <button
            type="button"
            onClick={openCreate}
            className="shrink-0 rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white"
          >
            New connection
          </button>
        )}
      </div>

      {err && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {String(err)}
        </div>
      )}

      {(mode === 'create' || mode === 'edit') && (
        <div className="rounded-2xl border border-[var(--color-border)] bg-stone-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/40">
          <h2 className={SECTION_TITLE}>
            {mode === 'create' ? 'New connection' : 'Edit connection'}
          </h2>
          <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
            {serverTypeLabel(form.server_type)} — adjust fields for your engine; use Advanced JSON for Soda-only
            options (OAuth, ODBC flags, etc.).
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-[var(--color-ink-muted)]">Name</span>
              <input
                value={form.name}
                onChange={(e) => setF('name', e.target.value)}
                className={inputClass}
                disabled={busy}
              />
            </label>
            <label className="block text-sm">
              <span className="text-[var(--color-ink-muted)]">Server type</span>
              <select
                value={form.server_type}
                onChange={(e) => setF('server_type', e.target.value)}
                className={inputClass}
                disabled={busy}
              >
                {CONNECTION_SERVER_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {serverTypeLabel(t)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-[var(--color-ink-muted)]">Description</span>
              <input
                value={form.description}
                onChange={(e) => setF('description', e.target.value)}
                className={inputClass}
                disabled={busy}
                placeholder="e.g. Cloud SQL prod"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[var(--color-ink-muted)]">Host</span>
              <input
                value={form.host}
                onChange={(e) => setF('host', e.target.value)}
                className={inputClass}
                disabled={busy}
              />
            </label>
            <label className="block text-sm">
              <span className="text-[var(--color-ink-muted)]">Port</span>
              <input
                value={form.port}
                onChange={(e) => setF('port', e.target.value)}
                inputMode="numeric"
                placeholder="5432"
                className={inputClass}
                disabled={busy}
              />
            </label>
            <label className="block text-sm">
              <span className="text-[var(--color-ink-muted)]">Database</span>
              <input
                value={form.database}
                onChange={(e) => setF('database', e.target.value)}
                className={inputClass}
                disabled={busy}
              />
            </label>
            <label className="block text-sm">
              <span className="text-[var(--color-ink-muted)]">Schema</span>
              <input
                value={form.schema_name}
                onChange={(e) => setF('schema_name', e.target.value)}
                className={inputClass}
                disabled={busy}
                placeholder="public / dbo / …"
              />
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-[var(--color-ink-muted)]">Username</span>
              <input
                value={form.username}
                onChange={(e) => setF('username', e.target.value)}
                className={inputClass}
                disabled={busy}
              />
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-[var(--color-ink-muted)]">Password</span>
              <input
                type="password"
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => setF('password', e.target.value)}
                placeholder={mode === 'edit' ? 'Leave blank to keep existing' : 'Optional'}
                className={inputClass}
                disabled={busy}
              />
            </label>

            {showSnowflake && (
              <>
                <label className="block text-sm">
                  <span className="text-[var(--color-ink-muted)]">Account</span>
                  <input
                    value={form.account}
                    onChange={(e) => setF('account', e.target.value)}
                    className={inputClass}
                    disabled={busy}
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-[var(--color-ink-muted)]">Warehouse</span>
                  <input
                    value={form.warehouse}
                    onChange={(e) => setF('warehouse', e.target.value)}
                    className={inputClass}
                    disabled={busy}
                  />
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-[var(--color-ink-muted)]">Role</span>
                  <input
                    value={form.role}
                    onChange={(e) => setF('role', e.target.value)}
                    className={inputClass}
                    disabled={busy}
                  />
                </label>
              </>
            )}

            {showBigQuery && (
              <>
                <label className="block text-sm">
                  <span className="text-[var(--color-ink-muted)]">Project ID</span>
                  <input
                    value={form.project}
                    onChange={(e) => setF('project', e.target.value)}
                    className={inputClass}
                    disabled={busy}
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-[var(--color-ink-muted)]">Dataset (BigQuery)</span>
                  <input
                    value={form.dataset}
                    onChange={(e) => setF('dataset', e.target.value)}
                    className={inputClass}
                    disabled={busy}
                  />
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-[var(--color-ink-muted)]">Location</span>
                  <input
                    value={form.location}
                    onChange={(e) => setF('location', e.target.value)}
                    className={inputClass}
                    disabled={busy}
                    placeholder="e.g. US"
                  />
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-[var(--color-ink-muted)]">Service account JSON</span>
                  <textarea
                    value={form.service_account_json}
                    onChange={(e) => setF('service_account_json', e.target.value)}
                    rows={4}
                    className={`${inputClass} font-mono text-xs`}
                    disabled={busy}
                    placeholder="{ ... }"
                  />
                </label>
              </>
            )}

            {showCatalog && (
              <>
                <label className="block text-sm">
                  <span className="text-[var(--color-ink-muted)]">Catalog</span>
                  <input
                    value={form.catalog}
                    onChange={(e) => setF('catalog', e.target.value)}
                    className={inputClass}
                    disabled={busy}
                  />
                </label>
              </>
            )}

            {showMotherduck && (
              <>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-[var(--color-ink-muted)]">MotherDuck token</span>
                  <input
                    type="password"
                    autoComplete="new-password"
                    value={form.token}
                    onChange={(e) => setF('token', e.target.value)}
                    placeholder={mode === 'edit' ? 'Leave blank to keep existing' : ''}
                    className={inputClass}
                    disabled={busy}
                  />
                </label>
              </>
            )}

            <label className="block text-sm sm:col-span-2">
              <span className="text-[var(--color-ink-muted)]">Advanced: extra params (JSON)</span>
              <textarea
                value={form.extra_params_json}
                onChange={(e) => setF('extra_params_json', e.target.value)}
                rows={5}
                className={`${inputClass} font-mono text-xs`}
                disabled={busy}
                placeholder={
                  showMysqlWire
                    ? '{\n  "charset": "utf8mb4",\n  "use_unicode": true\n}'
                    : '{\n  "oauth": { ... }\n}'
                }
              />
              <span className="mt-1 block text-xs text-[var(--color-ink-muted)]">
                Merged into the Soda data source block (e.g. Trino OAuth, Snowflake session_parameters).
                {showMysqlWire
                  ? ' For MySQL/ClickHouse (Soda), optional charset, use_unicode, and collation are applied to DQ scans.'
                  : ''}
              </span>
            </label>
          </div>

          {testResult && (
            <div
              role="status"
              className={`mt-4 rounded-xl border p-3 text-sm ${
                testResult.ok
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100'
                  : 'border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200'
              }`}
            >
              {testResult.ok ? 'Connection succeeded.' : 'Connection failed.'}
              {testResult.message ? (
                <span className="mt-1 block font-mono text-xs opacity-90">{testResult.message}</span>
              ) : null}
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => testMut.mutate()}
              className="rounded-full border border-[var(--color-border)] px-4 py-2 text-sm font-medium dark:border-zinc-700"
            >
              {testMut.isPending ? 'Testing…' : 'Test connection'}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => (mode === 'create' ? createMut.mutate() : patchMut.mutate())}
              className="rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {createMut.isPending || patchMut.isPending ? 'Saving…' : mode === 'create' ? 'Create' : 'Save changes'}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={cancel}
              className="rounded-full border border-[var(--color-border)] px-4 py-2 text-sm dark:border-zinc-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {listQuery.isLoading && (
        <p className="text-sm text-[var(--color-ink-muted)]">Loading connections…</p>
      )}

      {!listQuery.isLoading && items.length === 0 && mode === 'idle' && (
        <div className="rounded-2xl border border-dashed border-[var(--color-border)] bg-stone-50/50 p-10 text-center dark:border-zinc-700 dark:bg-zinc-900/20">
          <p className="text-[var(--color-ink-muted)]">No connections yet.</p>
          <button
            type="button"
            onClick={openCreate}
            className="mt-4 rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white"
          >
            Add connection
          </button>
        </div>
      )}

      {items.length > 0 && (
        <ul className="grid gap-4 lg:grid-cols-2">
          {items.map((c) => (
            <li
              key={c.id}
              className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] p-4 dark:border-zinc-800"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className={CARD_TITLE}>{c.name}</h3>
                  <p className="mt-1 font-mono text-xs text-[var(--color-ink-muted)]">
                    {serverTypeLabel(c.server_type)}
                    {c.host && ` · ${c.host}`}
                    {c.database && ` / ${c.database}`}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--color-ink-muted)]">
                    {c.has_password && (
                      <span className="rounded-full bg-stone-200 px-2 py-0.5 dark:bg-zinc-800">password</span>
                    )}
                    {c.has_token && (
                      <span className="rounded-full bg-stone-200 px-2 py-0.5 dark:bg-zinc-800">token</span>
                    )}
                    {c.has_service_account_json && (
                      <span className="rounded-full bg-stone-200 px-2 py-0.5 dark:bg-zinc-800">json key</span>
                    )}
                  </div>
                </div>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => openEdit(c)}
                    className="rounded-lg px-2 py-1 text-xs font-medium text-teal-700 dark:text-teal-400"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (
                        window.confirm(
                          `Delete connection “${c.name}”? Fails if a data quality check still uses it.`,
                        )
                      ) {
                        deleteMut.mutate(c.id)
                      }
                    }}
                    className="rounded-lg px-2 py-1 text-xs font-medium text-red-700 dark:text-red-400"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
