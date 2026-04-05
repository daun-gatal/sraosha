/**
 * API base URL: empty uses relative URLs (Vite dev proxy → FastAPI).
 * Production: set `VITE_API_BASE_URL=https://your-api-host`.
 */
export function apiBaseUrl(): string {
  const b = import.meta.env.VITE_API_BASE_URL ?? ''
  return b.replace(/\/$/, '')
}

function buildUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${apiBaseUrl()}${p}`
}

async function readError(res: Response): Promise<never> {
  const errBody = await res.text()
  throw new Error(`${res.status} ${res.statusText}: ${errBody.slice(0, 400)}`)
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(buildUrl(path), {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) await readError(res)
  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  })
  if (!res.ok) await readError(res)
  if (res.status === 204) return undefined as T
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: 'PUT',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) await readError(res)
  if (res.status === 204) return undefined as T
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: 'PATCH',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) await readError(res)
  if (res.status === 204) return undefined as T
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(buildUrl(path), { method: 'DELETE' })
  if (!res.ok) await readError(res)
}
