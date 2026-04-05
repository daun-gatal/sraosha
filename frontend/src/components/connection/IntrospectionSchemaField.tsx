import {
  connectionUsesSchemaForIntrospection,
  defaultSchemaForIntrospection,
  resolveIntrospectionSchema,
} from '../../pages/settings/serverTypes'

type Props = {
  serverType: string | undefined
  connectionSchemaName: string | null | undefined
  schemaOverride: string | null
  onSchemaOverrideChange: (value: string | null) => void
  disabled?: boolean
}

/**
 * Schema/catalog for listing tables is taken from the connection by default.
 * Shown only for sources that use a schema namespace (e.g. PostgreSQL). Other
 * engine types resolve a default in code without exposing a field.
 */
export function IntrospectionSchemaField({
  serverType,
  connectionSchemaName,
  schemaOverride,
  onSchemaOverrideChange,
  disabled = false,
}: Props) {
  const st = serverType || 'postgres'
  if (!connectionUsesSchemaForIntrospection(st)) {
    return null
  }

  const derived = defaultSchemaForIntrospection(st, connectionSchemaName)
  const resolved = resolveIntrospectionSchema(st, connectionSchemaName, schemaOverride)

  const inputClass =
    'mt-1 w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950'

  return (
    <div className="block text-sm">
      <span className="text-[var(--color-ink-muted)]">Schema</span>
      {schemaOverride === null ? (
        <div className="mt-1">
          <p className="rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950">
            {resolved}
          </p>
          <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
            From this connection’s default (edit the connection to change it). Override only if you need
            another namespace for introspection here.
          </p>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onSchemaOverrideChange(derived)}
            className="mt-2 text-xs font-medium text-teal-700 hover:underline disabled:opacity-50 dark:text-teal-400"
          >
            Use a different schema…
          </button>
        </div>
      ) : (
        <div className="mt-1 space-y-2">
          <input
            value={schemaOverride}
            onChange={(e) => onSchemaOverrideChange(e.target.value)}
            className={inputClass}
            disabled={disabled}
            spellCheck={false}
            aria-label="Schema override"
          />
          <button
            type="button"
            disabled={disabled}
            onClick={() => onSchemaOverrideChange(null)}
            className="text-xs font-medium text-teal-700 hover:underline disabled:opacity-50 dark:text-teal-400"
          >
            Use connection default
          </button>
        </div>
      )}
    </div>
  )
}
