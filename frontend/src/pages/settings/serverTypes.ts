/**
 * Must match `SUPPORTED_CONNECTION_SERVER_TYPES` in
 * `sraosha/core/connection_server_types.py` when adding database types.
 */
export const CONNECTION_SERVER_TYPES: readonly string[] = [
  'postgres',
  'mysql',
  'bigquery',
  'clickhouse',
  'mssql',
  'motherduck',
  'presto',
  'oracle',
  'redshift',
  'snowflake',
  'trino',
]

const LABELS: Record<string, string> = {
  postgres: 'PostgreSQL',
  mysql: 'MySQL',
  bigquery: 'BigQuery',
  clickhouse: 'ClickHouse (MySQL wire)',
  mssql: 'Microsoft SQL Server',
  motherduck: 'MotherDuck',
  presto: 'Presto',
  oracle: 'Oracle',
  redshift: 'Amazon Redshift',
  snowflake: 'Snowflake',
  trino: 'Trino',
}

export function serverTypeLabel(serverType: string | undefined): string {
  const s = (serverType || '').trim().toLowerCase()
  return LABELS[s] || serverType || 'unknown'
}

/**
 * Whether to show the “schema” override in the contract/DQ guided builder for
 * engines that use a SQL schema namespace similar to Postgres.
 */
export function connectionUsesSchemaForIntrospection(serverType: string | undefined): boolean {
  const s = (serverType || '').trim().toLowerCase()
  return (
    s === 'postgres' ||
    s === 'postgresql' ||
    s === 'cloudsql' ||
    s === 'mssql' ||
    s === 'oracle' ||
    s === 'redshift' ||
    s === 'snowflake'
  )
}

/**
 * Default schema/catalog for introspection, mirroring backend defaults.
 */
export function defaultSchemaForIntrospection(
  serverType: string | undefined,
  schemaNameOnConnection: string | null | undefined,
): string {
  const s = (serverType || '').trim().toLowerCase()
  if (s === 'postgres' || s === 'postgresql' || s === 'cloudsql') {
    return schemaNameOnConnection?.trim() || 'public'
  }
  if (s === 'mysql' || s === 'clickhouse') {
    return schemaNameOnConnection?.trim() || ''
  }
  if (s === 'mssql' || s === 'sqlserver') {
    return schemaNameOnConnection?.trim() || 'dbo'
  }
  if (s === 'oracle') {
    return schemaNameOnConnection?.trim() || ''
  }
  if (s === 'redshift' || s === 'snowflake') {
    return schemaNameOnConnection?.trim() || 'public'
  }
  if (s === 'duckdb') {
    return 'main'
  }
  if (s === 'trino' || s === 'presto') {
    return schemaNameOnConnection?.trim() || ''
  }
  return 'public'
}

/** Resolved schema for API URLs: connection default unless the user set an override. */
export function resolveIntrospectionSchema(
  serverType: string | undefined,
  connectionSchemaName: string | null | undefined,
  schemaOverride: string | null,
): string {
  const derived = defaultSchemaForIntrospection(serverType, connectionSchemaName)
  if (schemaOverride === null) return derived
  return schemaOverride.trim() || derived
}

/** Read-only hint for connection selects: server label · host · database */
export function connectionSummaryLine(c: {
  server_type: string
  host: string | null
  database: string | null
}): string {
  const parts: string[] = [serverTypeLabel(c.server_type)]
  if (c.host?.trim()) parts.push(c.host.trim())
  if (c.database?.trim()) parts.push(c.database.trim())
  return parts.join(' · ')
}
