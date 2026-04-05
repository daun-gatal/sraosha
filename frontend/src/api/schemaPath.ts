/**
 * URL path segments cannot be empty. MySQL (and similar) use an empty logical schema
 * for the default database; encode that for /tables/{schema}/{table}/columns.
 */
export const EMPTY_SCHEMA_PATH_TOKEN = '__sraosha_empty__'

export function encodeSchemaPathSegment(schema: string): string {
  const t = schema.trim()
  return encodeURIComponent(t || EMPTY_SCHEMA_PATH_TOKEN)
}
