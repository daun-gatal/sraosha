import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiDelete, apiGet, apiPatch, apiPost } from '../../api/client'
import { CARD_TITLE, SECTION_TITLE } from '../../ui/titleStyles'

type Team = {
  id: string
  name: string
  default_alerting_profile_id: string | null
  created_at: string
  updated_at: string
}

type ProfileOpt = { id: string; name: string }

export function TeamsSettingsPage() {
  const qc = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Team | null>(null)
  const [name, setName] = useState('')
  const [profileId, setProfileId] = useState('')

  const teamsQuery = useQuery({
    queryKey: ['teams'],
    queryFn: () => apiGet<Team[]>('/api/v1/teams'),
  })

  const profilesQuery = useQuery({
    queryKey: ['alerting-profiles'],
    queryFn: () =>
      apiGet<{ items: ProfileOpt[] }>('/api/v1/alerting-profiles').then((r) => r.items),
  })

  const resetForm = () => {
    setName('')
    setProfileId('')
    setEditing(null)
    setFormOpen(false)
  }

  const openCreate = () => {
    setEditing(null)
    setName('')
    setProfileId('')
    setFormOpen(true)
  }

  const openEdit = (t: Team) => {
    setEditing(t)
    setName(t.name)
    setProfileId(t.default_alerting_profile_id ?? '')
    setFormOpen(true)
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const body = {
        name: name.trim(),
        default_alerting_profile_id: profileId ? profileId : null,
      }
      if (!body.name) throw new Error('Name is required')
      if (editing) {
        return apiPatch<Team>(`/api/v1/teams/${editing.id}`, body)
      }
      return apiPost<Team>('/api/v1/teams', body)
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['teams'] })
      resetForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiDelete(`/api/v1/teams/${id}`),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['teams'] })
    },
  })

  const teams = teamsQuery.data ?? []
  const profiles = profilesQuery.data ?? []
  const busy = saveMutation.isPending || deleteMutation.isPending
  const err =
    teamsQuery.error || profilesQuery.error || saveMutation.error || deleteMutation.error

  const profileLabel = (id: string | null) => {
    if (!id) return '—'
    const p = profiles.find((x) => x.id === id)
    return p?.name ?? id.slice(0, 8)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="text-sm text-[var(--color-ink-muted)]">
          Teams group ownership for contracts and checks. Optional default alerting profile applies when
          resources do not pick one explicitly.
        </p>
        <button
          type="button"
          onClick={openCreate}
          className="shrink-0 rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 dark:bg-teal-500"
        >
          Add team
        </button>
      </div>

      {err && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {String(err)}
        </div>
      )}

      {formOpen && (
        <div className="rounded-2xl border border-[var(--color-border)] bg-stone-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/40">
          <h2 className={SECTION_TITLE}>{editing ? 'Edit team' : 'New team'}</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-[var(--color-ink-muted)]">Name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
                disabled={busy}
              />
            </label>
            <label className="block text-sm">
              <span className="text-[var(--color-ink-muted)]">Default alerting profile</span>
              <select
                value={profileId}
                onChange={(e) => setProfileId(e.target.value)}
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
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => saveMutation.mutate()}
              className="rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {saveMutation.isPending ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={resetForm}
              className="rounded-full border border-[var(--color-border)] px-4 py-2 text-sm dark:border-zinc-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {teamsQuery.isLoading && (
        <p className="text-sm text-[var(--color-ink-muted)]">Loading teams…</p>
      )}

      {!teamsQuery.isLoading && teams.length === 0 && (
        <div className="rounded-2xl border border-dashed border-[var(--color-border)] bg-stone-50/50 p-10 text-center dark:border-zinc-700 dark:bg-zinc-900/20">
          <p className="text-[var(--color-ink-muted)]">No teams yet.</p>
          <button
            type="button"
            onClick={openCreate}
            className="mt-4 rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white"
          >
            Create your first team
          </button>
        </div>
      )}

      {teams.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2">
          {teams.map((t) => (
            <li
              key={t.id}
              className="flex flex-col rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] p-4 shadow-sm dark:border-zinc-800"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className={CARD_TITLE}>{t.name}</h3>
                  <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                    Default alerts: {profileLabel(t.default_alerting_profile_id)}
                  </p>
                  <p className="mt-2 text-xs text-[var(--color-ink-muted)]">
                    Updated {new Date(t.updated_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    onClick={() => openEdit(t)}
                    className="rounded-lg px-2 py-1 text-xs font-medium text-teal-700 hover:bg-teal-50 dark:text-teal-400 dark:hover:bg-teal-950/40"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (
                        window.confirm(
                          `Delete team “${t.name}”? This fails if contracts or DQ checks still reference it.`,
                        )
                      ) {
                        deleteMutation.mutate(t.id)
                      }
                    }}
                    className="rounded-lg px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/40"
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
