import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPost, apiPut } from '../../api/client'
import { encodeSchemaPathSegment } from '../../api/schemaPath'
import { IntrospectionSchemaField } from '../../components/connection/IntrospectionSchemaField'
import { YamlEditor } from '../../components/editors/YamlEditor'
import {
  connectionSummaryLine,
  connectionUsesSchemaForIntrospection,
  resolveIntrospectionSchema,
} from '../settings/serverTypes'
import { mergeSodaclChecksForBlocks } from './mergeSodaclYaml'
import { FIELD_GROUP_LABEL, PAGE_TITLE, SUBSECTION_TITLE } from '../../ui/titleStyles'

type TeamOpt = { id: string; name: string }
type ProfileOpt = { id: string; name: string }
type ConnOpt = {
  id: string
  name: string
  server_type: string
  schema_name: string | null
  host: string | null
  database: string | null
}
type TableRow = { name: string; kind: string }
type ColRow = { name: string; suggested_field_type: string }
type DQTemplate = {
  key: string
  label: string
  description: string
  needs_column: boolean
  params: Array<{ name: string; label: string; type: string; default?: string; placeholder?: string }>
}

type DQCheck = {
  id: string
  name: string
  description: string | null
  connection_id: string
  team_id: string | null
  alerting_profile_id: string | null
  data_source_name: string
  sodacl_yaml: string
  tables: string[]
  check_categories: string[]
  tags: string[]
  is_enabled: boolean
}

type DQDetailPayload = { check: DQCheck; recent_runs: unknown[] }

function linesToList(text: string): string[] {
  return text
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function listToLines(list: string[] | undefined): string {
  return (list ?? []).join('\n')
}

export function DataQualityEditorPage() {
  const { checkId } = useParams<{ checkId: string }>()
  const isNew = !checkId
  const navigate = useNavigate()
  const qc = useQueryClient()

  const detailQuery = useQuery({
    queryKey: ['dq-check', checkId],
    queryFn: () => apiGet<DQDetailPayload>(`/api/v1/data-quality/${checkId}`),
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

  const connectionsQuery = useQuery({
    queryKey: ['connections'],
    queryFn: () => apiGet<{ items: ConnOpt[] }>('/api/v1/connections').then((r) => r.items),
  })

  const teams = teamsQuery.data ?? []
  const profiles = profilesQuery.data ?? []
  const connections = connectionsQuery.data ?? []

  const listError = useMemo(() => {
    const e = teamsQuery.error || profilesQuery.error || connectionsQuery.error
    return e ? String(e) : null
  }, [teamsQuery.error, profilesQuery.error, connectionsQuery.error])

  if (!isNew && detailQuery.isLoading) {
    return <p className="text-[var(--color-ink-muted)]">Loading check…</p>
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
      <DQNewForm
        teams={teams}
        profiles={profiles}
        connections={connections}
        listError={listError}
        navigate={navigate}
        qc={qc}
      />
    )
  }

  const initial = detailQuery.data?.check
  if (!initial) return null

  return (
    <DQEditForm
      key={checkId}
      checkId={checkId!}
      initial={initial}
      teams={teams}
      profiles={profiles}
      connections={connections}
      listError={listError}
      navigate={navigate}
      qc={qc}
    />
  )
}

function DQNewForm(props: {
  teams: TeamOpt[]
  profiles: ProfileOpt[]
  connections: ConnOpt[]
  listError: string | null
  navigate: ReturnType<typeof useNavigate>
  qc: ReturnType<typeof useQueryClient>
}) {
  const { teams, profiles, connections, listError, navigate, qc } = props

  const templatesQuery = useQuery({
    queryKey: ['dq-check-templates'],
    queryFn: () => apiGet<{ items: DQTemplate[] }>('/api/v1/data-quality/check-templates'),
  })
  const templateList = templatesQuery.data?.items ?? []

  const [name, setName] = useState('')
  const [connectionId, setConnectionId] = useState('')
  const [dataSourceName, setDataSourceName] = useState('')
  const [sodaclYaml, setSodaclYaml] = useState('')
  const [description, setDescription] = useState('')
  const [teamId, setTeamId] = useState('')
  const [alertingProfileId, setAlertingProfileId] = useState('')
  const [categoriesText, setCategoriesText] = useState('')
  const [tagsText, setTagsText] = useState('')
  const [advancedSodaOpen, setAdvancedSodaOpen] = useState(false)

  const [schemaOverride, setSchemaOverride] = useState<string | null>(null)
  const [tableName, setTableName] = useState('')
  const [tables, setTables] = useState<TableRow[]>([])
  const [columns, setColumns] = useState<ColRow[]>([])
  const [selectedTpl, setSelectedTpl] = useState<Record<string, boolean>>({})
  const [paramVals, setParamVals] = useState<Record<string, Record<string, string>>>({})
  const [colPerTpl, setColPerTpl] = useState<Record<string, string>>({})

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
    },
  })

  const loadColumnsMut = useMutation({
    mutationFn: async () => {
      if (!connectionId || !tableName.trim()) throw new Error('Choose a table')
      const sch = introspectionSchema
      return apiGet<{ items: ColRow[] }>(
        `/api/v1/connections/${connectionId}/tables/${encodeSchemaPathSegment(sch)}/${encodeURIComponent(tableName.trim())}/columns`,
      )
    },
    onSuccess: (data) => {
      setColumns(
        data.items.map((c) => ({
          name: c.name,
          suggested_field_type: c.suggested_field_type,
        })),
      )
    },
  })

  const toggleTpl = (key: string, on: boolean) => {
    setSelectedTpl((prev) => ({ ...prev, [key]: on }))
    if (on) {
      const meta = templateList.find((t) => t.key === key)
      if (meta) {
        setParamVals((prev) => {
          const row = { ...(prev[key] || {}) }
          for (const p of meta.params) {
            if (row[p.name] === undefined) row[p.name] = p.default ?? ''
          }
          return { ...prev, [key]: row }
        })
      }
    }
  }

  const generateMut = useMutation({
    mutationFn: async () => {
      const keys = Object.keys(selectedTpl).filter((k) => selectedTpl[k])
      if (keys.length === 0) throw new Error('Select at least one check template')
      if (!tableName.trim()) throw new Error('Choose a table and load columns')
      const tname = tableName.trim()
      const parts: string[] = []
      for (const key of keys) {
        const meta = templateList.find((t) => t.key === key)
        if (!meta) continue
        if (meta.needs_column) {
          const col = colPerTpl[key]
          if (!col) throw new Error(`Choose a column for: ${meta.label}`)
        }
        const rawParams = paramVals[key] || {}
        const params: Record<string, string | number> = { ...rawParams }
        for (const pk of Object.keys(params)) {
          const v = params[pk]
          if (v !== '' && v !== undefined && /^\d+$/.test(String(v))) {
            params[pk] = parseInt(String(v), 10)
          }
        }
        const r = await apiPost<{ sodacl_yaml: string }>('/api/v1/data-quality/preview-sodacl', {
          template_key: key,
          table: tname,
          column: meta.needs_column ? colPerTpl[key] : null,
          params,
        })
        parts.push(r.sodacl_yaml)
      }
      return mergeSodaclChecksForBlocks(parts)
    },
    onSuccess: (yaml) => {
      setSodaclYaml(yaml)
      if (!dataSourceName.trim()) setDataSourceName(tableName.trim().replace(/[^a-zA-Z0-9_]/g, '_').toLowerCase() || 'dataset')
      setAdvancedSodaOpen(true)
    },
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      const tables = tableName.trim() ? [tableName.trim()] : []
      const check_categories = linesToList(categoriesText)
      const tags = linesToList(tagsText)
      if (!name.trim()) throw new Error('Name is required')
      if (!connectionId) throw new Error('Connection is required')
      if (!sodaclYaml.trim()) throw new Error('Generate SodaCL first or paste in Advanced')
      if (!dataSourceName.trim()) throw new Error('Data source name is required')
      return apiPost<{ id: string }>('/api/v1/data-quality', {
        name: name.trim(),
        description: description.trim() || null,
        connection_id: connectionId,
        team_id: teamId || null,
        alerting_profile_id: alertingProfileId || null,
        data_source_name: dataSourceName.trim(),
        sodacl_yaml: sodaclYaml,
        tables,
        check_categories,
        tags,
      })
    },
    onSuccess: async (data) => {
      await qc.invalidateQueries({ queryKey: ['dq-checks'] })
      if (data && typeof data === 'object' && 'id' in data) {
        navigate(`/data-quality/${(data as { id: string }).id}`, { replace: true })
      }
    },
  })

  const busy =
    saveMutation.isPending ||
    loadTablesMut.isPending ||
    loadColumnsMut.isPending ||
    generateMut.isPending

  const errorBanner = useMemo(() => {
    const e =
      saveMutation.error ||
      loadTablesMut.error ||
      loadColumnsMut.error ||
      generateMut.error ||
      templatesQuery.error
    if (e) return String(e)
    return listError
  }, [
    saveMutation.error,
    loadTablesMut.error,
    loadColumnsMut.error,
    generateMut.error,
    templatesQuery.error,
    listError,
  ])

  const onPickConnection = (id: string) => {
    setConnectionId(id)
    setSchemaOverride(null)
    setTables([])
    setTableName('')
    setColumns([])
  }

  return (
    <DQFormChrome
      title="New DQ Check"
      busy={busy}
      errorBanner={errorBanner}
      savePending={saveMutation.isPending}
      onSave={() => saveMutation.mutate()}
      showRun={false}
      showDelete={false}
      runPending={false}
      onRun={() => {}}
      onDelete={() => {}}
      runSuccessNote={null}
      subtitle="Choose connection and table, then select Soda check templates—no raw SodaCL required."
    >
      <div className="rounded-2xl border border-[var(--color-border)] bg-stone-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30">
        <h2 className={SUBSECTION_TITLE}>Guided checks</h2>
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
        <button
          type="button"
          disabled={busy || !connectionId}
          onClick={() => loadTablesMut.mutate()}
          className="mt-3 rounded-full bg-stone-200 px-3 py-1.5 text-sm dark:bg-zinc-800"
        >
          {loadTablesMut.isPending ? 'Loading…' : 'Load tables'}
        </button>
        {tables.length > 0 && (
          <label className="mt-4 block text-sm">
            <span className="text-[var(--color-ink-muted)]">Table (Soda dataset name)</span>
            <select
              value={tableName}
              onChange={(e) => {
                setTableName(e.target.value)
                setColumns([])
              }}
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

        {templateList.length > 0 && columns.length > 0 && (
          <div className="mt-6 space-y-4">
            <p className="text-xs text-[var(--color-ink-muted)]">
              Select one or more checks. Column-specific checks need a column from the list above.
            </p>
            {templateList.map((tm) => (
              <div
                key={tm.key}
                className="rounded-xl border border-[var(--color-border)] bg-white/80 p-3 dark:border-zinc-700 dark:bg-zinc-950/40"
              >
                <label className="flex cursor-pointer items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedTpl[tm.key] ?? false}
                    onChange={(e) => toggleTpl(tm.key, e.target.checked)}
                    className="mt-1"
                  />
                  <span>
                    <span className="font-medium">{tm.label}</span>
                    <span className="block text-xs text-[var(--color-ink-muted)]">{tm.description}</span>
                  </span>
                </label>
                {selectedTpl[tm.key] && tm.needs_column && (
                  <label className="mt-2 block text-sm">
                    <span className="text-[var(--color-ink-muted)]">Column</span>
                    <select
                      value={colPerTpl[tm.key] ?? ''}
                      onChange={(e) =>
                        setColPerTpl((prev) => ({ ...prev, [tm.key]: e.target.value }))
                      }
                      className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-2 py-1.5 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-950"
                    >
                      <option value="">— Select —</option>
                      {columns.map((c) => (
                        <option key={c.name} value={c.name}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {selectedTpl[tm.key] &&
                  tm.params.map((p) => (
                    <label key={p.name} className="mt-2 block text-sm">
                      <span className="text-[var(--color-ink-muted)]">{p.label}</span>
                      <input
                        value={paramVals[tm.key]?.[p.name] ?? p.default ?? ''}
                        onChange={(e) =>
                          setParamVals((prev) => ({
                            ...prev,
                            [tm.key]: { ...(prev[tm.key] || {}), [p.name]: e.target.value },
                          }))
                        }
                        placeholder={p.placeholder}
                        className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                      />
                    </label>
                  ))}
              </div>
            ))}
            <button
              type="button"
              disabled={busy}
              onClick={() => generateMut.mutate()}
              className="rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white dark:bg-teal-500"
            >
              {generateMut.isPending ? 'Generating…' : 'Generate SodaCL'}
            </button>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-3">
          <details
            open={advancedSodaOpen}
            onToggle={(e) => setAdvancedSodaOpen((e.target as HTMLDetailsElement).open)}
            className="rounded-2xl border border-[var(--color-border)] bg-stone-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30"
          >
            <summary className={`cursor-pointer ${SUBSECTION_TITLE}`}>
              Advanced: edit SodaCL directly
            </summary>
            <YamlEditor
              value={sodaclYaml}
              onChange={setSodaclYaml}
              disabled={busy}
              minHeight="16rem"
              placeholder="Generate from templates above, or paste SodaCL…"
              className="mt-3"
            />
          </details>
        </div>

        <DQFormSideBasics
          name={name}
          setName={setName}
          connectionId={connectionId}
          setConnectionId={setConnectionId}
          dataSourceName={dataSourceName}
          setDataSourceName={setDataSourceName}
          description={description}
          setDescription={setDescription}
          teamId={teamId}
          setTeamId={setTeamId}
          alertingProfileId={alertingProfileId}
          setAlertingProfileId={setAlertingProfileId}
          categoriesText={categoriesText}
          setCategoriesText={setCategoriesText}
          tagsText={tagsText}
          setTagsText={setTagsText}
          teams={teams}
          profiles={profiles}
          connections={connections}
          busy={busy}
          showEnabled={false}
          isEnabled
          setIsEnabled={() => {}}
        />
      </div>
    </DQFormChrome>
  )
}

function DQEditForm(props: {
  checkId: string
  initial: DQCheck
  teams: TeamOpt[]
  profiles: ProfileOpt[]
  connections: ConnOpt[]
  listError: string | null
  navigate: ReturnType<typeof useNavigate>
  qc: ReturnType<typeof useQueryClient>
}) {
  const { checkId, initial, teams, profiles, connections, listError, navigate, qc } = props

  const templatesQuery = useQuery({
    queryKey: ['dq-check-templates'],
    queryFn: () => apiGet<{ items: DQTemplate[] }>('/api/v1/data-quality/check-templates'),
  })
  const templateList = templatesQuery.data?.items ?? []

  const [name, setName] = useState(initial.name)
  const [connectionId, setConnectionId] = useState(initial.connection_id)
  const [dataSourceName, setDataSourceName] = useState(initial.data_source_name)
  const [sodaclYaml, setSodaclYaml] = useState(initial.sodacl_yaml)
  const [isEnabled, setIsEnabled] = useState(initial.is_enabled)
  const [description, setDescription] = useState(initial.description ?? '')
  const [teamId, setTeamId] = useState(initial.team_id ?? '')
  const [alertingProfileId, setAlertingProfileId] = useState(initial.alerting_profile_id ?? '')
  const [categoriesText, setCategoriesText] = useState(listToLines(initial.check_categories))
  const [tagsText, setTagsText] = useState(listToLines(initial.tags))

  const [schemaOverride, setSchemaOverride] = useState<string | null>(null)
  const [tableName, setTableName] = useState(initial.tables?.[0] ?? '')
  const [tables, setTables] = useState<TableRow[]>([])
  const [columns, setColumns] = useState<ColRow[]>([])
  const [selectedTpl, setSelectedTpl] = useState<Record<string, boolean>>({})
  const [paramVals, setParamVals] = useState<Record<string, Record<string, string>>>({})
  const [colPerTpl, setColPerTpl] = useState<Record<string, string>>({})

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
      setColumns([])
    },
  })

  const loadColumnsMut = useMutation({
    mutationFn: async () => {
      if (!connectionId || !tableName.trim()) throw new Error('Choose a table')
      const sch = introspectionSchema
      return apiGet<{ items: ColRow[] }>(
        `/api/v1/connections/${connectionId}/tables/${encodeSchemaPathSegment(sch)}/${encodeURIComponent(tableName.trim())}/columns`,
      )
    },
    onSuccess: (data) => {
      setColumns(
        data.items.map((c) => ({
          name: c.name,
          suggested_field_type: c.suggested_field_type,
        })),
      )
    },
  })

  const toggleTpl = (key: string, on: boolean) => {
    setSelectedTpl((prev) => ({ ...prev, [key]: on }))
    if (on) {
      const meta = templateList.find((t) => t.key === key)
      if (meta) {
        setParamVals((prev) => {
          const row = { ...(prev[key] || {}) }
          for (const p of meta.params) {
            if (row[p.name] === undefined) row[p.name] = p.default ?? ''
          }
          return { ...prev, [key]: row }
        })
      }
    }
  }

  const generateMut = useMutation({
    mutationFn: async () => {
      const keys = Object.keys(selectedTpl).filter((k) => selectedTpl[k])
      if (keys.length === 0) throw new Error('Select at least one check template')
      if (!tableName.trim()) throw new Error('Choose a table and load columns')
      const tname = tableName.trim()
      const parts: string[] = []
      for (const key of keys) {
        const meta = templateList.find((t) => t.key === key)
        if (!meta) continue
        if (meta.needs_column) {
          const col = colPerTpl[key]
          if (!col) throw new Error(`Choose a column for: ${meta.label}`)
        }
        const rawParams = paramVals[key] || {}
        const params: Record<string, string | number> = { ...rawParams }
        for (const pk of Object.keys(params)) {
          const v = params[pk]
          if (v !== '' && v !== undefined && /^\d+$/.test(String(v))) {
            params[pk] = parseInt(String(v), 10)
          }
        }
        const r = await apiPost<{ sodacl_yaml: string }>('/api/v1/data-quality/preview-sodacl', {
          template_key: key,
          table: tname,
          column: meta.needs_column ? colPerTpl[key] : null,
          params,
        })
        parts.push(r.sodacl_yaml)
      }
      return mergeSodaclChecksForBlocks(parts)
    },
    onSuccess: (yaml) => setSodaclYaml(yaml),
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      const tables = tableName.trim() ? [tableName.trim()] : []
      const check_categories = linesToList(categoriesText)
      const tags = linesToList(tagsText)
      return apiPut(`/api/v1/data-quality/${checkId}`, {
        name: name.trim() || undefined,
        description: description.trim() || null,
        connection_id: connectionId || undefined,
        team_id: teamId || null,
        alerting_profile_id: alertingProfileId || null,
        data_source_name: dataSourceName.trim() || undefined,
        sodacl_yaml: sodaclYaml,
        tables,
        check_categories,
        tags,
        is_enabled: isEnabled,
      })
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['dq-checks'] })
      await qc.invalidateQueries({ queryKey: ['dq-check', checkId] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => apiDelete(`/api/v1/data-quality/${checkId}`),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['dq-checks'] })
      navigate('/data-quality')
    },
  })

  const runMutation = useMutation({
    mutationFn: () => apiPost<{ task_id: string; status: string }>(`/api/v1/data-quality/${checkId}/run`),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['dq-check', checkId] })
      await qc.invalidateQueries({ queryKey: ['dq-checks'] })
    },
  })

  const busy =
    saveMutation.isPending ||
    deleteMutation.isPending ||
    runMutation.isPending ||
    loadTablesMut.isPending ||
    loadColumnsMut.isPending ||
    generateMut.isPending

  const errorBanner = useMemo(() => {
    const e =
      saveMutation.error ||
      deleteMutation.error ||
      runMutation.error ||
      loadTablesMut.error ||
      loadColumnsMut.error ||
      generateMut.error ||
      templatesQuery.error
    if (e) return String(e)
    return listError
  }, [
    saveMutation.error,
    deleteMutation.error,
    runMutation.error,
    loadTablesMut.error,
    loadColumnsMut.error,
    generateMut.error,
    templatesQuery.error,
    listError,
  ])

  const runNote =
    runMutation.isSuccess && !runMutation.isPending && runMutation.data ? (
      <span>
        Scan queued (task {runMutation.data.task_id}). Refresh runs or the list for status.
      </span>
    ) : null

  const onPickConnection = (id: string) => {
    setConnectionId(id)
    setSchemaOverride(null)
    setTables([])
    setTableName('')
    setColumns([])
  }

  return (
    <DQFormChrome
      title={name || 'DQ check'}
      busy={busy}
      errorBanner={errorBanner}
      savePending={saveMutation.isPending}
      onSave={() => saveMutation.mutate()}
      showRun
      showDelete
      runPending={runMutation.isPending}
      onRun={() => runMutation.mutate()}
      onDelete={() => {
        if (window.confirm(`Delete DQ check “${name}”?`)) deleteMutation.mutate()
      }}
      runSuccessNote={runNote}
      subtitle={undefined}
      scheduleTo={`/schedules?focus=dq&checkId=${encodeURIComponent(checkId)}`}
    >
      <details className="rounded-2xl border border-[var(--color-border)] bg-stone-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30">
        <summary className={`cursor-pointer ${SUBSECTION_TITLE}`}>
          Regenerate SodaCL from templates
        </summary>
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
        <button
          type="button"
          disabled={busy || !connectionId}
          onClick={() => loadTablesMut.mutate()}
          className="mt-3 rounded-full bg-stone-200 px-3 py-1.5 text-sm dark:bg-zinc-800"
        >
          {loadTablesMut.isPending ? 'Loading…' : 'Load tables'}
        </button>
        {tables.length > 0 && (
          <label className="mt-4 block text-sm">
            <span className="text-[var(--color-ink-muted)]">Table</span>
            <select
              value={tableName}
              onChange={(e) => {
                setTableName(e.target.value)
                setColumns([])
              }}
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
        {templateList.length > 0 && columns.length > 0 && (
          <div className="mt-4 space-y-3">
            {templateList.map((tm) => (
              <div key={tm.key} className="rounded-lg border border-[var(--color-border)] bg-white/80 p-2 dark:border-zinc-700 dark:bg-zinc-900/50">
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedTpl[tm.key] ?? false}
                    onChange={(e) => toggleTpl(tm.key, e.target.checked)}
                  />
                  <span>{tm.label}</span>
                </label>
                {selectedTpl[tm.key] && tm.needs_column && (
                  <select
                    value={colPerTpl[tm.key] ?? ''}
                    onChange={(e) =>
                      setColPerTpl((prev) => ({ ...prev, [tm.key]: e.target.value }))
                    }
                    className="mt-2 w-full rounded border border-[var(--color-border)] bg-white px-2 py-1 font-mono text-xs text-[var(--color-ink)] dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                  >
                    <option value="">— Column —</option>
                    {columns.map((c) => (
                      <option key={c.name} value={c.name}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                )}
                {selectedTpl[tm.key] &&
                  tm.params.map((p) => (
                    <input
                      key={p.name}
                      value={paramVals[tm.key]?.[p.name] ?? p.default ?? ''}
                      onChange={(e) =>
                        setParamVals((prev) => ({
                          ...prev,
                          [tm.key]: { ...(prev[tm.key] || {}), [p.name]: e.target.value },
                        }))
                      }
                      placeholder={p.label}
                      className="mt-1 w-full rounded border border-[var(--color-border)] bg-white px-2 py-1 text-xs text-[var(--color-ink)] dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                    />
                  ))}
              </div>
            ))}
            <button
              type="button"
              disabled={busy}
              onClick={() => generateMut.mutate()}
              className="rounded-full bg-teal-600 px-4 py-2 text-sm text-white dark:bg-teal-500"
            >
              {generateMut.isPending ? 'Generating…' : 'Replace SodaCL'}
            </button>
          </div>
        )}
      </details>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-3">
          <label className={`block ${FIELD_GROUP_LABEL}`}>SodaCL</label>
          <YamlEditor
            value={sodaclYaml}
            onChange={setSodaclYaml}
            disabled={busy}
            minHeight="24rem"
          />
        </div>

        <DQFormSideBasics
          name={name}
          setName={setName}
          connectionId={connectionId}
          setConnectionId={setConnectionId}
          dataSourceName={dataSourceName}
          setDataSourceName={setDataSourceName}
          description={description}
          setDescription={setDescription}
          teamId={teamId}
          setTeamId={setTeamId}
          alertingProfileId={alertingProfileId}
          setAlertingProfileId={setAlertingProfileId}
          categoriesText={categoriesText}
          setCategoriesText={setCategoriesText}
          tagsText={tagsText}
          setTagsText={setTagsText}
          teams={teams}
          profiles={profiles}
          connections={connections}
          busy={busy}
          showEnabled
          isEnabled={isEnabled}
          setIsEnabled={setIsEnabled}
        />
      </div>
    </DQFormChrome>
  )
}

function DQFormChrome(props: {
  title: string
  subtitle?: string
  children: React.ReactNode
  busy: boolean
  errorBanner: string | null
  savePending: boolean
  onSave: () => void
  showRun: boolean
  showDelete: boolean
  runPending: boolean
  onRun: () => void
  onDelete: () => void
  runSuccessNote: ReactNode
  scheduleTo?: string
}) {
  const {
    title,
    subtitle,
    children,
    busy,
    errorBanner,
    savePending,
    onSave,
    showRun,
    showDelete,
    runPending,
    onRun,
    onDelete,
    runSuccessNote,
    scheduleTo,
  } = props

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-[var(--color-ink-muted)]">
            <Link to="/data-quality" className="text-teal-700 hover:underline dark:text-teal-400">
              ← Data Quality
            </Link>
          </p>
          <h1 className={`mt-2 ${PAGE_TITLE}`}>{title}</h1>
          {subtitle && (
            <p className="mt-1 max-w-2xl text-sm text-[var(--color-ink-muted)]">{subtitle}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {scheduleTo && (
            <Link
              to={scheduleTo}
              className="rounded-full border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-[var(--color-ink)] hover:bg-stone-200 dark:border-zinc-700 dark:hover:bg-zinc-800"
            >
              Schedule
            </Link>
          )}
          {showRun && (
            <button
              type="button"
              disabled={busy}
              onClick={onRun}
              className="rounded-full bg-stone-200 px-4 py-2 text-sm font-medium text-stone-900 hover:bg-stone-300 disabled:opacity-50 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700"
            >
              {runPending ? 'Queueing…' : 'Run scan'}
            </button>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={onSave}
            className="rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50 dark:bg-teal-500 dark:hover:bg-teal-600"
          >
            {savePending ? 'Saving…' : 'Save'}
          </button>
          {showDelete && (
            <button
              type="button"
              disabled={busy}
              onClick={onDelete}
              className="rounded-full border border-red-300 px-4 py-2 text-sm font-medium text-red-800 hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/40"
            >
              Delete
            </button>
          )}
        </div>
      </div>

      {errorBanner && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {errorBanner}
        </div>
      )}
      {runSuccessNote && (
        <p className="text-sm text-teal-800 dark:text-teal-300">{runSuccessNote}</p>
      )}

      {children}
    </div>
  )
}

function DQFormSideBasics(props: {
  name: string
  setName: (v: string) => void
  connectionId: string
  setConnectionId: (v: string) => void
  dataSourceName: string
  setDataSourceName: (v: string) => void
  description: string
  setDescription: (v: string) => void
  teamId: string
  setTeamId: (v: string) => void
  alertingProfileId: string
  setAlertingProfileId: (v: string) => void
  categoriesText: string
  setCategoriesText: (v: string) => void
  tagsText: string
  setTagsText: (v: string) => void
  teams: TeamOpt[]
  profiles: ProfileOpt[]
  connections: ConnOpt[]
  busy: boolean
  showEnabled: boolean
  isEnabled: boolean
  setIsEnabled: (v: boolean) => void
}) {
  const p = props

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-[var(--color-border)] bg-stone-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30">
        <h2 className={SUBSECTION_TITLE}>Basics</h2>
        <div className="mt-3 space-y-4">
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Name</span>
            <input
              value={p.name}
              onChange={(e) => p.setName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={p.busy}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Connection</span>
            <select
              value={p.connectionId}
              onChange={(e) => p.setConnectionId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={p.busy}
            >
              <option value="">— Select —</option>
              {p.connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.server_type})
                </option>
              ))}
            </select>
            {p.connectionId &&
              (() => {
                const sel = p.connections.find((x) => x.id === p.connectionId)
                return sel ? (
                  <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                    {connectionSummaryLine(sel)}
                  </p>
                ) : null
              })()}
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Data source name</span>
            <input
              value={p.dataSourceName}
              onChange={(e) => p.setDataSourceName(e.target.value)}
              placeholder="Scan / dataset identifier for Soda"
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950"
              disabled={p.busy}
            />
          </label>
          {p.showEnabled && (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={p.isEnabled}
                onChange={(e) => p.setIsEnabled(e.target.checked)}
                disabled={p.busy}
              />
              <span>Enabled</span>
            </label>
          )}
        </div>
      </div>

      <details className="rounded-2xl border border-[var(--color-border)] bg-stone-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30">
        <summary className={`cursor-pointer ${SUBSECTION_TITLE}`}>
          Advanced
        </summary>
        <div className="mt-4 space-y-4">
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Description</span>
            <textarea
              value={p.description}
              onChange={(e) => p.setDescription(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              disabled={p.busy}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Team</span>
            <select
              value={p.teamId}
              onChange={(e) => p.setTeamId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={p.busy}
            >
              <option value="">— None —</option>
              {p.teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Alerting profile</span>
            <select
              value={p.alertingProfileId}
              onChange={(e) => p.setAlertingProfileId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={p.busy}
            >
              <option value="">— None —</option>
              {p.profiles.map((pr) => (
                <option key={pr.id} value={pr.id}>
                  {pr.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Check categories</span>
            <textarea
              value={p.categoriesText}
              onChange={(e) => p.setCategoriesText(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-950"
              disabled={p.busy}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Tags</span>
            <textarea
              value={p.tagsText}
              onChange={(e) => p.setTagsText(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-950"
              disabled={p.busy}
            />
          </label>
        </div>
      </details>
    </div>
  )
}
