import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { apiDelete, apiGet, apiPatch, apiPost } from '../../api/client'
import { SECTION_TITLE, SUBSECTION_TITLE } from '../../ui/titleStyles'

type Channel = {
  id: string
  alerting_profile_id: string
  channel_type: string
  config: Record<string, unknown>
  is_enabled: boolean
  sort_order: number
}

type Profile = {
  id: string
  name: string
  description: string | null
  channels: Channel[]
  created_at: string
  updated_at: string
}

const CHANNEL_TYPES = ['slack', 'email', 'webhook'] as const

export function AlertingSettingsPage() {
  const qc = useQueryClient()
  const [expanded, setExpanded] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [editName, setEditName] = useState('')
  const [editDesc, setEditDesc] = useState('')

  const [chType, setChType] = useState<(typeof CHANNEL_TYPES)[number]>('slack')
  const [chSlack, setChSlack] = useState('')
  const [chEmail, setChEmail] = useState('')
  const [chUrl, setChUrl] = useState('')
  const [chEnabled, setChEnabled] = useState(true)

  const [editChId, setEditChId] = useState<string | null>(null)
  const [editChType, setEditChType] = useState<(typeof CHANNEL_TYPES)[number]>('slack')
  const [editSlack, setEditSlack] = useState('')
  const [editEmail, setEditEmail] = useState('')
  const [editUrl, setEditUrl] = useState('')
  const [editChEnabled, setEditChEnabled] = useState(true)

  const listQuery = useQuery({
    queryKey: ['alerting-profiles'],
    queryFn: () => apiGet<{ items: Profile[] }>('/api/v1/alerting-profiles'),
  })

  const profileItems = listQuery.data?.items
  const profiles = profileItems ?? []

  const selected = useMemo(() => {
    if (!expanded || !profileItems) return null
    return profileItems.find((p) => p.id === expanded) ?? null
  }, [expanded, profileItems])

  const openProfile = (p: Profile) => {
    setExpanded(p.id)
    setEditName(p.name)
    setEditDesc(p.description ?? '')
    setEditChId(null)
    resetChannelForm()
    resetEditChannelForm()
  }

  const resetChannelForm = () => {
    setChType('slack')
    setChSlack('')
    setChEmail('')
    setChUrl('')
    setChEnabled(true)
  }

  const resetEditChannelForm = () => {
    setEditChId(null)
    setEditChType('slack')
    setEditSlack('')
    setEditEmail('')
    setEditUrl('')
    setEditChEnabled(true)
  }

  function buildConfig(
    type: (typeof CHANNEL_TYPES)[number],
    slack: string,
    email: string,
    url: string,
  ): Record<string, string> {
    if (type === 'slack') return { channel: slack.trim() }
    if (type === 'email') return { to: email.trim() }
    return { url: url.trim() }
  }

  const createProfileMut = useMutation({
    mutationFn: () =>
      apiPost<Profile>('/api/v1/alerting-profiles', {
        name: newName.trim(),
        description: newDesc.trim() || null,
        channels: [],
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['alerting-profiles'] })
      setNewName('')
      setNewDesc('')
    },
  })

  const patchProfileMut = useMutation({
    mutationFn: () => {
      if (!expanded) throw new Error('No profile')
      return apiPatch<Profile>(`/api/v1/alerting-profiles/${expanded}`, {
        name: editName.trim(),
        description: editDesc.trim() || null,
      })
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['alerting-profiles'] })
    },
  })

  const deleteProfileMut = useMutation({
    mutationFn: (id: string) => apiDelete(`/api/v1/alerting-profiles/${id}`),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['alerting-profiles'] })
      setExpanded(null)
    },
  })

  const addChannelMut = useMutation({
    mutationFn: () => {
      if (!expanded) throw new Error('No profile')
      const config = buildConfig(chType, chSlack, chEmail, chUrl)
      return apiPost<Channel>(`/api/v1/alerting-profiles/${expanded}/channels`, {
        channel_type: chType,
        config,
        is_enabled: chEnabled,
        sort_order: 0,
      })
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['alerting-profiles'] })
      resetChannelForm()
    },
  })

  const patchChannelMut = useMutation({
    mutationFn: () => {
      if (!expanded || !editChId) throw new Error('No channel')
      const config = buildConfig(editChType, editSlack, editEmail, editUrl)
      return apiPatch<Channel>(
        `/api/v1/alerting-profiles/${expanded}/channels/${editChId}`,
        {
          channel_type: editChType,
          config,
          is_enabled: editChEnabled,
        },
      )
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['alerting-profiles'] })
      resetEditChannelForm()
    },
  })

  const deleteChannelMut = useMutation({
    mutationFn: ({ pid, cid }: { pid: string; cid: string }) =>
      apiDelete(`/api/v1/alerting-profiles/${pid}/channels/${cid}`),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['alerting-profiles'] })
      resetEditChannelForm()
    },
  })

  const busy =
    createProfileMut.isPending ||
    patchProfileMut.isPending ||
    deleteProfileMut.isPending ||
    addChannelMut.isPending ||
    patchChannelMut.isPending ||
    deleteChannelMut.isPending

  const err =
    listQuery.error ||
    createProfileMut.error ||
    patchProfileMut.error ||
    deleteProfileMut.error ||
    addChannelMut.error ||
    patchChannelMut.error ||
    deleteChannelMut.error

  const startEditChannel = (c: Channel) => {
    setEditChId(c.id)
    setEditChType(c.channel_type as (typeof CHANNEL_TYPES)[number])
    setEditChEnabled(c.is_enabled)
    const cfg = c.config as Record<string, string>
    setEditSlack(cfg.channel ?? cfg.slack_channel ?? '')
    setEditEmail(cfg.to ?? cfg.email ?? '')
    setEditUrl(cfg.url ?? '')
  }

  return (
    <div className="space-y-8">
      <p className="text-sm text-[var(--color-ink-muted)]">
        Alerting profiles group notification channels (Slack, email, webhooks). Attach them to teams,
        contracts, or DQ checks.
      </p>

      {err && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {String(err)}
        </div>
      )}

      <section className="rounded-2xl border border-[var(--color-border)] bg-stone-50/50 p-5 dark:border-zinc-800 dark:bg-zinc-900/30">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 className={SECTION_TITLE}>New alerting profile</h2>
          <button
            type="button"
            disabled={busy || !newName.trim()}
            onClick={() => createProfileMut.mutate()}
            className="shrink-0 rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {createProfileMut.isPending ? 'Creating…' : 'Create profile'}
          </button>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-[var(--color-ink-muted)]">Name</span>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="text-[var(--color-ink-muted)]">Description</span>
            <input
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              disabled={busy}
            />
          </label>
        </div>
      </section>

      {listQuery.isLoading && <p className="text-sm text-[var(--color-ink-muted)]">Loading…</p>}

      {!listQuery.isLoading && profiles.length === 0 && (
        <p className="text-sm text-[var(--color-ink-muted)]">No alerting profiles yet. Create one above.</p>
      )}

      <ul className="space-y-4">
        {profiles.map((p) => (
          <li
            key={p.id}
            className="overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] dark:border-zinc-800"
          >
            <button
              type="button"
              onClick={() => (expanded === p.id ? setExpanded(null) : openProfile(p))}
              className="flex w-full items-center justify-between gap-4 px-4 py-4 text-left hover:bg-stone-50 dark:hover:bg-zinc-900/50"
            >
              <div>
                <span className="font-semibold">{p.name}</span>
                {p.description && (
                  <span className="mt-1 block text-sm text-[var(--color-ink-muted)]">{p.description}</span>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {p.channels.map((c) => (
                  <span
                    key={c.id}
                    className="rounded-full bg-stone-200 px-2 py-0.5 text-xs font-medium dark:bg-zinc-800"
                  >
                    {c.channel_type}
                    {!c.is_enabled && ' (off)'}
                  </span>
                ))}
                <span className="text-[var(--color-ink-muted)]">{expanded === p.id ? '▼' : '▶'}</span>
              </div>
            </button>

            {expanded === p.id && selected && (
              <div className="space-y-6 border-t border-[var(--color-border)] bg-stone-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/20">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="grid flex-1 gap-3 sm:grid-cols-2">
                    <label className="block text-sm">
                      <span className="text-[var(--color-ink-muted)]">Name</span>
                      <input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
                        disabled={busy}
                      />
                    </label>
                    <label className="block text-sm sm:col-span-2">
                      <span className="text-[var(--color-ink-muted)]">Description</span>
                      <input
                        value={editDesc}
                        onChange={(e) => setEditDesc(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
                        disabled={busy}
                      />
                    </label>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => patchProfileMut.mutate()}
                      className="rounded-full bg-teal-600 px-3 py-1.5 text-sm text-white"
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        if (window.confirm(`Delete profile “${p.name}” and all its channels?`)) {
                          deleteProfileMut.mutate(p.id)
                        }
                      }}
                      className="rounded-full border border-red-300 px-3 py-1.5 text-sm text-red-800 dark:border-red-800 dark:text-red-300"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                <div>
                  <h3 className={SUBSECTION_TITLE}>Channels</h3>
                  <ul className="mt-2 space-y-2">
                    {selected.channels.map((c) => (
                      <li
                        key={c.id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--color-border)] bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                      >
                        <span className="font-mono text-xs">
                          {c.channel_type} · {c.is_enabled ? 'on' : 'off'}
                        </span>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            className="text-teal-700 text-xs dark:text-teal-400"
                            onClick={() => startEditChannel(c)}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="text-xs text-red-700 dark:text-red-400"
                            onClick={() => {
                              if (window.confirm('Remove this channel?')) {
                                deleteChannelMut.mutate({ pid: p.id, cid: c.id })
                              }
                            }}
                          >
                            Remove
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>

                  {editChId && (
                    <div className="mt-4 rounded-xl border border-teal-200 bg-teal-50/50 p-3 dark:border-teal-900 dark:bg-teal-950/20">
                      <p className="text-xs font-medium text-teal-900 dark:text-teal-200">Edit channel</p>
                      <div className="mt-2 grid gap-2 sm:grid-cols-2">
                        <label className="block text-sm">
                          <span className="text-[var(--color-ink-muted)]">Type</span>
                          <select
                            value={editChType}
                            onChange={(e) =>
                              setEditChType(e.target.value as (typeof CHANNEL_TYPES)[number])
                            }
                            className="mt-1 w-full rounded border border-[var(--color-border)] bg-white px-2 py-1 text-[var(--color-ink)] dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                          >
                            {CHANNEL_TYPES.map((t) => (
                              <option key={t} value={t}>
                                {t}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={editChEnabled}
                            onChange={(e) => setEditChEnabled(e.target.checked)}
                          />
                          Enabled
                        </label>
                        {editChType === 'slack' && (
                          <label className="block text-sm sm:col-span-2">
                            <span className="text-[var(--color-ink-muted)]">Slack channel</span>
                            <input
                              value={editSlack}
                              onChange={(e) => setEditSlack(e.target.value)}
                              placeholder="#alerts or channel ID"
                              className="mt-1 w-full rounded border border-[var(--color-border)] bg-white px-2 py-1 text-[var(--color-ink)] dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                            />
                          </label>
                        )}
                        {editChType === 'email' && (
                          <label className="block text-sm sm:col-span-2">
                            <span className="text-[var(--color-ink-muted)]">Email to</span>
                            <input
                              value={editEmail}
                              onChange={(e) => setEditEmail(e.target.value)}
                              className="mt-1 w-full rounded border border-[var(--color-border)] bg-white px-2 py-1 text-[var(--color-ink)] dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                            />
                          </label>
                        )}
                        {editChType === 'webhook' && (
                          <label className="block text-sm sm:col-span-2">
                            <span className="text-[var(--color-ink-muted)]">Webhook URL</span>
                            <input
                              value={editUrl}
                              onChange={(e) => setEditUrl(e.target.value)}
                              className="mt-1 w-full rounded border border-[var(--color-border)] bg-white px-2 py-1 text-[var(--color-ink)] dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                            />
                          </label>
                        )}
                      </div>
                      <div className="mt-2 flex gap-2">
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => patchChannelMut.mutate()}
                          className="rounded-full bg-teal-600 px-3 py-1 text-xs text-white"
                        >
                          Update channel
                        </button>
                        <button
                          type="button"
                          onClick={resetEditChannelForm}
                          className="rounded-full border px-3 py-1 text-xs"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  <div className="mt-4 rounded-xl border border-dashed border-[var(--color-border)] p-3 dark:border-zinc-700">
                    <p className="text-xs font-medium text-[var(--color-ink-muted)]">Add channel</p>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      <label className="block text-sm">
                        <span className="text-[var(--color-ink-muted)]">Type</span>
                        <select
                          value={chType}
                          onChange={(e) => setChType(e.target.value as (typeof CHANNEL_TYPES)[number])}
                          className="mt-1 w-full rounded border border-[var(--color-border)] bg-white px-2 py-1 text-[var(--color-ink)] dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                          disabled={busy}
                        >
                          {CHANNEL_TYPES.map((t) => (
                            <option key={t} value={t}>
                              {t}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={chEnabled}
                          onChange={(e) => setChEnabled(e.target.checked)}
                          disabled={busy}
                        />
                        Enabled
                      </label>
                      {chType === 'slack' && (
                        <label className="block text-sm sm:col-span-2">
                          <span className="text-[var(--color-ink-muted)]">Slack channel</span>
                          <input
                            value={chSlack}
                            onChange={(e) => setChSlack(e.target.value)}
                            placeholder="#alerts"
                            className="mt-1 w-full rounded border border-[var(--color-border)] bg-white px-2 py-1 text-[var(--color-ink)] dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                            disabled={busy}
                          />
                        </label>
                      )}
                      {chType === 'email' && (
                        <label className="block text-sm sm:col-span-2">
                          <span className="text-[var(--color-ink-muted)]">Email to</span>
                          <input
                            value={chEmail}
                            onChange={(e) => setChEmail(e.target.value)}
                            className="mt-1 w-full rounded border border-[var(--color-border)] bg-white px-2 py-1 text-[var(--color-ink)] dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                            disabled={busy}
                          />
                        </label>
                      )}
                      {chType === 'webhook' && (
                        <label className="block text-sm sm:col-span-2">
                          <span className="text-[var(--color-ink-muted)]">Webhook URL</span>
                          <input
                            value={chUrl}
                            onChange={(e) => setChUrl(e.target.value)}
                            className="mt-1 w-full rounded border border-[var(--color-border)] bg-white px-2 py-1 text-[var(--color-ink)] dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                            disabled={busy}
                          />
                        </label>
                      )}
                    </div>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => addChannelMut.mutate()}
                      className="mt-3 rounded-full bg-stone-800 px-3 py-1.5 text-xs font-medium text-white dark:bg-zinc-200 dark:text-zinc-900"
                    >
                      Add channel
                    </button>
                  </div>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
