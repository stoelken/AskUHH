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

/**
 * Stream a query via SSE.
 * @param {string} question
 * @param {object} callbacks
 * @param {function} callbacks.onSources  - called once with sources array
 * @param {function} callbacks.onToken    - called per token string
 * @param {function} callbacks.onDone     - called when stream finishes
 * @param {function} callbacks.onError    - called on error
 * @param {AbortSignal} [signal]          - optional abort signal
 */
async function queryStream(question, { onSources, onToken, onDone, onError }, signal) {
  const res = await fetch(`${BASE}/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
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

    // Parse SSE events from the buffer
    const parts = buffer.split('\n\n')
    buffer = parts.pop() // keep the incomplete part

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
          case 'error':
            onError?.(new Error(parsed))
            break
        }
      } catch {
        // ignore malformed JSON
      }
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
  query: (question, signal) =>
    request('/query', {
      method: 'POST',
      body: JSON.stringify({ question }),
      ...(signal ? { signal } : {}),
    }),
  queryStream,
}
