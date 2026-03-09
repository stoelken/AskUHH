const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  status: () => request('/status'),
  ingest: () => request('/ingest', { method: 'POST' }),
  query:  (question, signal) => request('/query', {
    method: 'POST',
    body: JSON.stringify({ question }),
    ...(signal ? { signal } : {}),
  }),
}
