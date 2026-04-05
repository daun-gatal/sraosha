/**
 * SodaCL snippets from `/preview-sodacl` each start with `checks for <table>:`.
 * Concatenating them produces duplicate YAML keys for the same table. Merge
 * bodies under a single `checks for …` block per table.
 */
export function mergeSodaclChecksForBlocks(snippets: string[]): string {
  const byTable = new Map<string, string[]>()
  const extras: string[] = []

  for (const raw of snippets) {
    const trimmed = raw.trim()
    if (!trimmed) continue
    const lines = trimmed.split('\n')
    const m = /^checks for (\S+):\s*$/.exec((lines[0] ?? '').trim())
    if (!m) {
      extras.push(trimmed)
      continue
    }
    const table = m[1]
    const body = lines.slice(1)
    const acc = byTable.get(table)
    if (acc) acc.push(...body)
    else byTable.set(table, [...body])
  }

  const out: string[] = []
  for (const [table, bodyLines] of byTable) {
    out.push(`checks for ${table}:`)
    out.push(...bodyLines)
    out.push('')
  }
  let result = out.join('\n').trimEnd()
  if (extras.length > 0) {
    const extraBlock = extras.join('\n\n')
    result = result ? `${result}\n\n${extraBlock}` : extraBlock
  }
  return result
}
