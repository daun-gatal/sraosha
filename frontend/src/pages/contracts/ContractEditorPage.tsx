import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { IntrospectionSchemaField } from '../../components/connection/IntrospectionSchemaField'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPost, apiPut } from '../../api/client'
import { encodeSchemaPathSegment } from '../../api/schemaPath'
import { YamlEditor } from '../../components/editors/YamlEditor'
import {
  connectionSummaryLine,
  connectionUsesSchemaForIntrospection,
  resolveIntrospectionSchema,
} from '../settings/serverTypes'
import { FIELD_GROUP_LABEL, PAGE_TITLE, SUBSECTION_TITLE } from '../../ui/titleStyles'

const ENFORCEMENT_MODES = ['block', 'warn', 'log'] as const

/** Matches backend `default_contract_file_path` for display when creating a contract. */
function defaultContractFilePath(contractId: string): string {
  const safe = contractId.trim().replace(/[^a-zA-Z0-9._-]+/g, '_') || 'contract'
  return `contracts/${safe}.yaml`
}

type TeamOpt = { id: string; name: string }
type ProfileOpt = { id: string; name: string }
type ConnRow = {
  id: string
  name: string
  schema_name: string | null
  server_type: string
  host: string | null
  database: string | null
}
type TableRow = { name: string; kind: string }
type ColRow = {
  name: string
  data_type: string
  is_nullable: boolean
  suggested_field_type: string
}

type ContractDetail = {
  contract_id: string
  title: string
  description: string | null
  file_path: string
  team_id: string | null
  alerting_profile_id: string | null
  enforcement_mode: string
  is_active: boolean
  raw_yaml: string
  spec_version: string | null
  info_version: string | null
}

export function ContractEditorPage() {
  const { contractId } = useParams<{ contractId: string }>()
  const isNew = !contractId
  const navigate = useNavigate()
  const qc = useQueryClient()

  const detailQuery = useQuery({
    queryKey: ['contract', contractId],
    queryFn: () => apiGet<ContractDetail>(`/api/v1/contracts/${contractId}`),
    enabled: !isNew,
  })

  const teamsQuery = useQuery({
    queryKey: ['teams'],
    queryFn: () => apiGet<TeamOpt[]>('/api/v1/teams'),
  })

  const profilesQuery = useQuery({
    queryKey: ['alerting-profiles'],
    queryFn: () => apiGet<{ items: ProfileOpt[] }>('/api/v1/alerting-profiles').then((r) => r.items),
  })

  const teams = teamsQuery.data ?? []
  const profiles = profilesQuery.data ?? []

  const listError = useMemo(() => {
    const e = teamsQuery.error || profilesQuery.error
    return e ? String(e) : null
  }, [teamsQuery.error, profilesQuery.error])

  if (!isNew && detailQuery.isLoading) {
    return <p className="text-[var(--color-ink-muted)]">Loading contract…</p>
  }
  if (!isNew && detailQuery.error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        {String(detailQuery.error)}
      </div>
    )
  }

  if (isNew) {
    return (
      <ContractNewForm
        teams={teams}
        profiles={profiles}
        listError={listError}
        navigate={navigate}
        qc={qc}
      />
    )
  }

  const initial = detailQuery.data
  if (!initial) return null

  return (
    <ContractEditForm
      key={contractId}
      contractId={contractId!}
      initial={initial}
      teams={teams}
      profiles={profiles}
      listError={listError}
      navigate={navigate}
      qc={qc}
    />
  )
}

function ContractNewForm(props: {
  teams: TeamOpt[]
  profiles: ProfileOpt[]
  listError: string | null
  navigate: ReturnType<typeof useNavigate>
  qc: ReturnType<typeof useQueryClient>
}) {
  const { teams, profiles, listError, navigate, qc } = props

  const connectionsQuery = useQuery({
    queryKey: ['connections'],
    queryFn: () => apiGet<{ items: ConnRow[] }>('/api/v1/connections').then((r) => r.items),
  })
  const connections = connectionsQuery.data ?? []

  const [contractIdInput, setContractIdInput] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [specVersion, setSpecVersion] = useState('1.1.0')
  const [infoVersion, setInfoVersion] = useState('1.0.0')
  const [enforcementMode, setEnforcementMode] = useState<string>('block')
  const [teamId, setTeamId] = useState<string>('')
  const [alertingProfileId, setAlertingProfileId] = useState<string>('')
  const [rawYaml, setRawYaml] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const [connectionId, setConnectionId] = useState('')
  const [schemaOverride, setSchemaOverride] = useState<string | null>(null)
  const [tableName, setTableName] = useState('')
  const [tables, setTables] = useState<TableRow[]>([])
  const [columns, setColumns] = useState<ColRow[]>([])
  const [colFlags, setColFlags] = useState<
    Record<string, { use: boolean; req: boolean; uniq: boolean }>
  >({})

  const selectedConn = useMemo(
    () => connections.find((x) => x.id === connectionId),
    [connections, connectionId],
  )
  const introspectionSchema = useMemo(
    () =>
      resolveIntrospectionSchema(selectedConn?.server_type, selectedConn?.schema_name, schemaOverride),
    [selectedConn, schemaOverride],
  )
  const showIntrospectionSchemaUi =
    Boolean(connectionId && selectedConn && connectionUsesSchemaForIntrospection(selectedConn.server_type))

  const loadTablesMut = useMutation({
    mutationFn: async () => {
      if (!connectionId) throw new Error('Choose a connection first')
      const sch = introspectionSchema
      return apiGet<{ items: { name: string; kind: string }[]; schema_name: string }>(
        `/api/v1/connections/${connectionId}/tables?schema=${encodeURIComponent(sch)}`,
      )
    },
    onSuccess: (data) => {
      setTables(data.items.map((t) => ({ name: t.name, kind: t.kind })))
      setTableName('')
      setColumns([])
      setColFlags({})
    },
  })

  const loadColumnsMut = useMutation({
    mutationFn: async () => {
      if (!connectionId || !tableName.trim()) throw new Error('Choose a table')
      const sch = introspectionSchema
      const t = tableName.trim()
      return apiGet<{ items: ColRow[]; schema_name: string; table_name: string }>(
        `/api/v1/connections/${connectionId}/tables/${encodeSchemaPathSegment(sch)}/${encodeURIComponent(t)}/columns`,
      )
    },
    onSuccess: (data) => {
      setColumns(data.items)
      const next: Record<string, { use: boolean; req: boolean; uniq: boolean }> = {}
      for (const c of data.items) {
        next[c.name] = { use: true, req: false, uniq: false }
      }
      setColFlags(next)
    },
  })

  const previewMut = useMutation({
    mutationFn: async () => {
      const cid = contractIdInput.trim()
      if (!cid) throw new Error('Contract ID is required')
      if (!connectionId) throw new Error('Choose a connection')
      if (!tableName.trim()) throw new Error('Choose a table')
      const cols = columns
        .filter((c) => colFlags[c.name]?.use)
        .map((c) => ({
          name: c.name,
          field_type: c.suggested_field_type,
          required: colFlags[c.name]?.req ?? false,
          unique: colFlags[c.name]?.uniq ?? false,
        }))
      if (cols.length === 0) throw new Error('Include at least one column')
      return apiPost<{ raw_yaml: string }>('/api/v1/contracts/preview-yaml', {
        connection_id: connectionId,
        contract_id: cid,
        title: title.trim() || cid,
        table_name: tableName.trim(),
        schema_name:
          schemaOverride === null ? null : schemaOverride.trim() ? schemaOverride.trim() : null,
        columns: cols,
        description: description.trim() || null,
        spec_version: specVersion.trim() || '1.1.0',
        version: infoVersion.trim() || '1.0.0',
        team_id: teamId || null,
        alerting_profile_id: alertingProfileId || null,
        enforcement_mode: enforcementMode,
      })
    },
    onSuccess: (data) => {
      setRawYaml(data.raw_yaml)
      setAdvancedOpen(true)
    },
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      const cid = contractIdInput.trim()
      if (!cid) throw new Error('Contract ID is required')
      if (!rawYaml.trim()) throw new Error('Generate the contract YAML first (guided builder or Advanced)')
      return apiPost<{ contract_id: string }>('/api/v1/contracts', {
        contract_id: cid,
        title: title.trim() || cid,
        description: description.trim() || null,
        team_id: teamId || null,
        alerting_profile_id: alertingProfileId || null,
        raw_yaml: rawYaml,
        enforcement_mode: enforcementMode,
      })
    },
    onSuccess: async (data) => {
      await qc.invalidateQueries({ queryKey: ['contracts'] })
      if (data && typeof data === 'object' && 'contract_id' in data) {
        navigate(`/contracts/${(data as { contract_id: string }).contract_id}`, { replace: true })
      }
    },
  })

  const busy =
    saveMutation.isPending ||
    loadTablesMut.isPending ||
    loadColumnsMut.isPending ||
    previewMut.isPending

  const errorBanner = useMemo(() => {
    const e =
      saveMutation.error ||
      loadTablesMut.error ||
      loadColumnsMut.error ||
      previewMut.error ||
      connectionsQuery.error
    if (e) return String(e)
    return listError
  }, [
    saveMutation.error,
    loadTablesMut.error,
    loadColumnsMut.error,
    previewMut.error,
    connectionsQuery.error,
    listError,
  ])

  const onPickConnection = (id: string) => {
    setConnectionId(id)
    setSchemaOverride(null)
    setTables([])
    setTableName('')
    setColumns([])
    setColFlags({})
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-[var(--color-ink-muted)]">
            <Link to="/contracts" className="text-teal-700 hover:underline dark:text-teal-400">
              ← Contracts
            </Link>
          </p>
          <h1 className={`mt-2 ${PAGE_TITLE}`}>
            New contract
          </h1>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)]">
            Pick a connection and table, then generate YAML—no manual editing required.
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => saveMutation.mutate()}
          className="rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50 dark:bg-teal-500 dark:hover:bg-teal-600"
        >
          {saveMutation.isPending ? 'Saving…' : 'Save'}
        </button>
      </header>

      {errorBanner && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {errorBanner}
        </div>
      )}

      <div className="rounded-2xl border border-[var(--color-border)] bg-stone-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30">
        <h2 className={SUBSECTION_TITLE}>Guided builder</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label
            className={`block text-sm ${!showIntrospectionSchemaUi ? 'sm:col-span-2' : ''}`}
          >
            <span className="text-[var(--color-ink-muted)]">Connection</span>
            <select
              value={connectionId}
              onChange={(e) => onPickConnection(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            >
              <option value="">— Select —</option>
              {connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.server_type})
                </option>
              ))}
            </select>
            {connectionId &&
              (() => {
                const sel = connections.find((x) => x.id === connectionId)
                return sel ? (
                  <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                    {connectionSummaryLine(sel)}
                  </p>
                ) : null
              })()}
          </label>
          {selectedConn && (
            <IntrospectionSchemaField
              serverType={selectedConn.server_type}
              connectionSchemaName={selectedConn.schema_name}
              schemaOverride={schemaOverride}
              onSchemaOverrideChange={setSchemaOverride}
              disabled={busy}
            />
          )}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy || !connectionId}
            onClick={() => loadTablesMut.mutate()}
            className="rounded-full bg-stone-200 px-3 py-1.5 text-sm font-medium dark:bg-zinc-800"
          >
            {loadTablesMut.isPending ? 'Loading…' : 'Load tables'}
          </button>
        </div>
        {tables.length > 0 && (
          <label className="mt-4 block text-sm">
            <span className="text-[var(--color-ink-muted)]">Table</span>
            <select
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            >
              <option value="">— Select —</option>
              {tables.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name} ({t.kind})
                </option>
              ))}
            </select>
          </label>
        )}
        {tables.length > 0 && (
          <div className="mt-3">
            <button
              type="button"
              disabled={busy || !tableName}
              onClick={() => loadColumnsMut.mutate()}
              className="rounded-full bg-stone-200 px-3 py-1.5 text-sm font-medium dark:bg-zinc-800"
            >
              {loadColumnsMut.isPending ? 'Loading…' : 'Load columns'}
            </button>
          </div>
        )}
        {columns.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[36rem] text-left text-xs">
              <thead>
                <tr className="border-b border-[var(--color-border)] dark:border-zinc-800">
                  <th className="py-2 pr-2">Include</th>
                  <th className="py-2 pr-2">Column</th>
                  <th className="py-2 pr-2">Type</th>
                  <th className="py-2 pr-2">Required</th>
                  <th className="py-2">Unique</th>
                </tr>
              </thead>
              <tbody>
                {columns.map((c) => (
                  <tr key={c.name} className="border-b border-stone-200/80 dark:border-zinc-800/80">
                    <td className="py-1.5 pr-2">
                      <input
                        type="checkbox"
                        checked={colFlags[c.name]?.use ?? true}
                        onChange={(e) =>
                          setColFlags((prev) => ({
                            ...prev,
                            [c.name]: {
                              use: e.target.checked,
                              req: prev[c.name]?.req ?? false,
                              uniq: prev[c.name]?.uniq ?? false,
                            },
                          }))
                        }
                      />
                    </td>
                    <td className="font-mono">{c.name}</td>
                    <td className="text-[var(--color-ink-muted)]">{c.suggested_field_type}</td>
                    <td className="pr-2">
                      <input
                        type="checkbox"
                        checked={colFlags[c.name]?.req ?? false}
                        onChange={(e) =>
                          setColFlags((prev) => ({
                            ...prev,
                            [c.name]: {
                              use: prev[c.name]?.use ?? true,
                              req: e.target.checked,
                              uniq: prev[c.name]?.uniq ?? false,
                            },
                          }))
                        }
                      />
                    </td>
                    <td>
                      <input
                        type="checkbox"
                        checked={colFlags[c.name]?.uniq ?? false}
                        onChange={(e) =>
                          setColFlags((prev) => ({
                            ...prev,
                            [c.name]: {
                              use: prev[c.name]?.use ?? true,
                              req: prev[c.name]?.req ?? false,
                              uniq: e.target.checked,
                            },
                          }))
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {columns.length > 0 && (
          <button
            type="button"
            disabled={busy}
            onClick={() => previewMut.mutate()}
            className="mt-4 rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50 dark:bg-teal-500"
          >
            {previewMut.isPending ? 'Generating…' : 'Generate contract YAML'}
          </button>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-3">
          <details
            open={advancedOpen}
            onToggle={(e) => setAdvancedOpen((e.target as HTMLDetailsElement).open)}
            className="rounded-2xl border border-[var(--color-border)] bg-stone-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30"
          >
            <summary className={`cursor-pointer ${SUBSECTION_TITLE}`}>
              Advanced: edit YAML directly
            </summary>
            <p className="mt-2 text-xs text-[var(--color-ink-muted)]">
              Optional. Generated YAML appears here; edit only if you need full control.
            </p>
            <YamlEditor
              value={rawYaml}
              onChange={setRawYaml}
              disabled={busy}
              minHeight="20rem"
              placeholder="Generate from the guided builder above, or paste YAML…"
              className="mt-3"
            />
          </details>
        </div>

        <div className="space-y-4 rounded-2xl border border-[var(--color-border)] bg-stone-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30">
          <h2 className={SUBSECTION_TITLE}>Details</h2>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Contract ID</span>
            <input
              value={contractIdInput}
              onChange={(e) => setContractIdInput(e.target.value)}
              placeholder="e.g. orders-v1"
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Title</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Description</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            />
          </label>
          <p className="text-sm text-[var(--color-ink-muted)]">
            <span className="block">Stored file path (set automatically)</span>
            <span className="mt-1 block font-mono text-xs text-[var(--color-ink)]">
              {contractIdInput.trim() ? defaultContractFilePath(contractIdInput) : '— enter a contract ID —'}
            </span>
          </p>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Data contract spec version</span>
            <input
              value={specVersion}
              onChange={(e) => setSpecVersion(e.target.value)}
              placeholder="1.1.0"
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Info version</span>
            <input
              value={infoVersion}
              onChange={(e) => setInfoVersion(e.target.value)}
              placeholder="1.0.0"
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Enforcement</span>
            <select
              value={enforcementMode}
              onChange={(e) => setEnforcementMode(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            >
              {ENFORCEMENT_MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Team</span>
            <select
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            >
              <option value="">— None —</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Alerting profile</span>
            <select
              value={alertingProfileId}
              onChange={(e) => setAlertingProfileId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            >
              <option value="">— None —</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
    </div>
  )
}

function ContractEditForm(props: {
  contractId: string
  initial: ContractDetail
  teams: TeamOpt[]
  profiles: ProfileOpt[]
  listError: string | null
  navigate: ReturnType<typeof useNavigate>
  qc: ReturnType<typeof useQueryClient>
}) {
  const { contractId, initial, teams, profiles, listError, navigate, qc } = props
  const [title, setTitle] = useState(initial.title)
  const [description, setDescription] = useState(initial.description ?? '')
  const [specVersion, setSpecVersion] = useState(initial.spec_version ?? '1.1.0')
  const [infoVersion, setInfoVersion] = useState(initial.info_version ?? '1.0.0')
  const [enforcementMode, setEnforcementMode] = useState(initial.enforcement_mode)
  const [teamId, setTeamId] = useState(initial.team_id ?? '')
  const [alertingProfileId, setAlertingProfileId] = useState(initial.alerting_profile_id ?? '')
  const [isActive, setIsActive] = useState(initial.is_active)
  const [rawYaml, setRawYaml] = useState(initial.raw_yaml)

  const connectionsQuery = useQuery({
    queryKey: ['connections'],
    queryFn: () => apiGet<{ items: ConnRow[] }>('/api/v1/connections').then((r) => r.items),
  })
  const connections = connectionsQuery.data ?? []

  const [connectionId, setConnectionId] = useState('')
  const [schemaOverride, setSchemaOverride] = useState<string | null>(null)
  const [tableName, setTableName] = useState('')
  const [tables, setTables] = useState<TableRow[]>([])
  const [columns, setColumns] = useState<ColRow[]>([])
  const [colFlags, setColFlags] = useState<
    Record<string, { use: boolean; req: boolean; uniq: boolean }>
  >({})

  const selectedConn = useMemo(
    () => connections.find((x) => x.id === connectionId),
    [connections, connectionId],
  )
  const introspectionSchema = useMemo(
    () =>
      resolveIntrospectionSchema(selectedConn?.server_type, selectedConn?.schema_name, schemaOverride),
    [selectedConn, schemaOverride],
  )
  const showIntrospectionSchemaUi =
    Boolean(connectionId && selectedConn && connectionUsesSchemaForIntrospection(selectedConn.server_type))

  const loadTablesMut = useMutation({
    mutationFn: async () => {
      if (!connectionId) throw new Error('Choose a connection')
      const sch = introspectionSchema
      return apiGet<{ items: { name: string; kind: string }[] }>(
        `/api/v1/connections/${connectionId}/tables?schema=${encodeURIComponent(sch)}`,
      )
    },
    onSuccess: (data) => {
      setTables(data.items.map((t) => ({ name: t.name, kind: t.kind })))
      setTableName('')
      setColumns([])
      setColFlags({})
    },
  })

  const loadColumnsMut = useMutation({
    mutationFn: async () => {
      if (!connectionId || !tableName.trim()) throw new Error('Choose a table')
      const sch = introspectionSchema
      const t = tableName.trim()
      return apiGet<{ items: ColRow[] }>(
        `/api/v1/connections/${connectionId}/tables/${encodeSchemaPathSegment(sch)}/${encodeURIComponent(t)}/columns`,
      )
    },
    onSuccess: (data) => {
      setColumns(data.items)
      const next: Record<string, { use: boolean; req: boolean; uniq: boolean }> = {}
      for (const c of data.items) {
        next[c.name] = { use: true, req: false, uniq: false }
      }
      setColFlags(next)
    },
  })

  const previewMut = useMutation({
    mutationFn: async () => {
      if (!connectionId || !tableName.trim()) throw new Error('Choose connection and table')
      const cols = columns
        .filter((c) => colFlags[c.name]?.use)
        .map((c) => ({
          name: c.name,
          field_type: c.suggested_field_type,
          required: colFlags[c.name]?.req ?? false,
          unique: colFlags[c.name]?.uniq ?? false,
        }))
      if (cols.length === 0) throw new Error('Include at least one column')
      return apiPost<{ raw_yaml: string }>('/api/v1/contracts/preview-yaml', {
        connection_id: connectionId,
        contract_id: contractId,
        title: title.trim() || contractId,
        table_name: tableName.trim(),
        schema_name:
          schemaOverride === null ? null : schemaOverride.trim() ? schemaOverride.trim() : null,
        columns: cols,
        description: description.trim() || null,
        spec_version: specVersion.trim() || '1.1.0',
        version: infoVersion.trim() || '1.0.0',
        team_id: teamId || null,
        alerting_profile_id: alertingProfileId || null,
        enforcement_mode: enforcementMode,
      })
    },
    onSuccess: (data) => setRawYaml(data.raw_yaml),
  })

  const saveMutation = useMutation({
    mutationFn: () =>
      apiPut(`/api/v1/contracts/${contractId}`, {
        title: title.trim() || undefined,
        description: description.trim() || null,
        team_id: teamId || null,
        alerting_profile_id: alertingProfileId || null,
        raw_yaml: rawYaml,
        enforcement_mode: enforcementMode,
        is_active: isActive,
        spec_version: specVersion.trim() || '1.1.0',
        info_version: infoVersion.trim() || '1.0.0',
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['contracts'] })
      await qc.invalidateQueries({ queryKey: ['contract', contractId] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () =>
      apiDelete(`/api/v1/contracts/${encodeURIComponent(contractId)}`),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['contracts'] })
      navigate('/contracts')
    },
  })

  const runMutation = useMutation({
    mutationFn: () => apiPost<Record<string, unknown>>(`/api/v1/contracts/${contractId}/run`),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['runs'] })
    },
  })

  const busy =
    saveMutation.isPending ||
    deleteMutation.isPending ||
    runMutation.isPending ||
    loadTablesMut.isPending ||
    loadColumnsMut.isPending ||
    previewMut.isPending

  const errorBanner = useMemo(() => {
    const e =
      saveMutation.error ||
      deleteMutation.error ||
      runMutation.error ||
      loadTablesMut.error ||
      loadColumnsMut.error ||
      previewMut.error ||
      connectionsQuery.error
    if (e) return String(e)
    return listError
  }, [
    saveMutation.error,
    deleteMutation.error,
    runMutation.error,
    loadTablesMut.error,
    loadColumnsMut.error,
    previewMut.error,
    connectionsQuery.error,
    listError,
  ])

  const onPickConnection = (id: string) => {
    setConnectionId(id)
    setSchemaOverride(null)
    setTables([])
    setTableName('')
    setColumns([])
    setColFlags({})
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-[var(--color-ink-muted)]">
            <Link to="/contracts" className="text-teal-700 hover:underline dark:text-teal-400">
              ← Contracts
            </Link>
          </p>
          <h1 className={`mt-2 ${PAGE_TITLE}`}>{contractId}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to={`/schedules?focus=contract&contractId=${encodeURIComponent(contractId)}`}
            className="rounded-full border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-[var(--color-ink)] hover:bg-stone-200 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            Schedule
          </Link>
          <button
            type="button"
            disabled={busy}
            onClick={() => runMutation.mutate()}
            className="rounded-full bg-stone-200 px-4 py-2 text-sm font-medium text-stone-900 hover:bg-stone-300 disabled:opacity-50 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700"
          >
            {runMutation.isPending ? 'Running…' : 'Run validation'}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => saveMutation.mutate()}
            className="rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50 dark:bg-teal-500 dark:hover:bg-teal-600"
          >
            {saveMutation.isPending ? 'Saving…' : 'Save'}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              if (window.confirm(`Delete contract “${contractId}”?`)) deleteMutation.mutate()
            }}
            className="rounded-full border border-red-300 px-4 py-2 text-sm font-medium text-red-800 hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/40"
          >
            Delete
          </button>
        </div>
      </div>

      {errorBanner && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {errorBanner}
        </div>
      )}
      {runMutation.isSuccess && !runMutation.isPending && (
        <p className="text-sm text-teal-800 dark:text-teal-300">Validation run recorded. Check Runs for results.</p>
      )}

      <details className="rounded-2xl border border-[var(--color-border)] bg-stone-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30">
        <summary className={`cursor-pointer ${SUBSECTION_TITLE}`}>
          Regenerate YAML from a connection
        </summary>
        <p className="mt-2 text-xs text-[var(--color-ink-muted)]">
          Reload tables and columns, then generate fresh YAML (replaces the editor content when you click Generate).
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label
            className={`block text-sm ${!showIntrospectionSchemaUi ? 'sm:col-span-2' : ''}`}
          >
            <span className="text-[var(--color-ink-muted)]">Connection</span>
            <select
              value={connectionId}
              onChange={(e) => onPickConnection(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            >
              <option value="">— Select —</option>
              {connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.server_type})
                </option>
              ))}
            </select>
            {connectionId &&
              (() => {
                const sel = connections.find((x) => x.id === connectionId)
                return sel ? (
                  <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                    {connectionSummaryLine(sel)}
                  </p>
                ) : null
              })()}
          </label>
          {selectedConn && (
            <IntrospectionSchemaField
              serverType={selectedConn.server_type}
              connectionSchemaName={selectedConn.schema_name}
              schemaOverride={schemaOverride}
              onSchemaOverrideChange={setSchemaOverride}
              disabled={busy}
            />
          )}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy || !connectionId}
            onClick={() => loadTablesMut.mutate()}
            className="rounded-full bg-stone-200 px-3 py-1.5 text-sm dark:bg-zinc-800"
          >
            {loadTablesMut.isPending ? 'Loading…' : 'Load tables'}
          </button>
        </div>
        {tables.length > 0 && (
          <label className="mt-4 block text-sm">
            <span className="text-[var(--color-ink-muted)]">Table</span>
            <select
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            >
              <option value="">— Select —</option>
              {tables.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {tables.length > 0 && (
          <button
            type="button"
            disabled={busy || !tableName}
            onClick={() => loadColumnsMut.mutate()}
            className="mt-3 rounded-full bg-stone-200 px-3 py-1.5 text-sm dark:bg-zinc-800"
          >
            {loadColumnsMut.isPending ? 'Loading…' : 'Load columns'}
          </button>
        )}
        {columns.length > 0 && (
          <button
            type="button"
            disabled={busy}
            onClick={() => previewMut.mutate()}
            className="mt-4 rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white dark:bg-teal-500"
          >
            {previewMut.isPending ? 'Generating…' : 'Generate and replace YAML'}
          </button>
        )}
      </details>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-3">
          <label className={`block ${FIELD_GROUP_LABEL}`}>Contract YAML</label>
          <YamlEditor
            value={rawYaml}
            onChange={setRawYaml}
            disabled={busy}
            minHeight="28rem"
          />
        </div>

        <div className="space-y-4 rounded-2xl border border-[var(--color-border)] bg-stone-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30">
          <h2 className={SUBSECTION_TITLE}>Details</h2>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Title</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Description</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            />
          </label>
          <p className="text-sm text-[var(--color-ink-muted)]">
            <span className="block">Stored file path</span>
            <span className="mt-1 block font-mono text-xs text-[var(--color-ink)]">{initial.file_path}</span>
          </p>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Data contract spec version</span>
            <input
              value={specVersion}
              onChange={(e) => setSpecVersion(e.target.value)}
              placeholder="1.1.0"
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Info version</span>
            <input
              value={infoVersion}
              onChange={(e) => setInfoVersion(e.target.value)}
              placeholder="1.0.0"
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Enforcement</span>
            <select
              value={enforcementMode}
              onChange={(e) => setEnforcementMode(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            >
              {ENFORCEMENT_MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Team</span>
            <select
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            >
              <option value="">— None —</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Alerting profile</span>
            <select
              value={alertingProfileId}
              onChange={(e) => setAlertingProfileId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            >
              <option value="">— None —</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              disabled={busy}
            />
            <span>Active</span>
          </label>
        </div>
      </div>
    </div>
  )
}
