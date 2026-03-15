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

async function queryStream(
  question,
  { onSources, onToken, onDone, onError, onFollowups },
  signal,
  history = []
) {
  const res = await fetch(`${BASE}/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, history }),
    signal,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    const parts = buffer.split('\n\n')
    buffer = parts.pop()

    for (const part of parts) {
      if (!part.trim()) continue

      let eventType = 'message'
      let data = ''

      for (const line of part.split('\n')) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          data = line.slice(6)
        }
      }

      if (!data) continue

      try {
        const parsed = JSON.parse(data)

        switch (eventType) {
          case 'sources':
            onSources?.(parsed)
            break
          case 'token':
            onToken?.(parsed)
            break
          case 'done':
            onDone?.(parsed)
            break
          case 'followups':
            onFollowups?.(parsed)
            break
          case 'error':
            onError?.(new Error(parsed))
            break
        }
      } catch {}
    }
  }
}

export const api = {
  status: () => request('/status'),
  ingest: () => request('/ingest', { method: 'POST' }),
  uploadDocuments: async (files) => {
    const formData = new FormData()
    for (const file of files) {
      formData.append('files', file)
    }

    const res = await fetch(`${BASE}/documents/upload`, {
      method: 'POST',
      body: formData,
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'Upload failed')
    }
    return res.json()
  },
  deleteDocument: (filename) =>
    request(`/documents/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
    }),
  queryStream,
}
