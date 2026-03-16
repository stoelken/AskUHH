import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'

// Custom hook that fetches backend status and exposes loading/error + refresh.
export function useStatus() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Re-fetches server status and updates all hook states.
  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.status()
      setStatus(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { status, loading, error, refresh }
}
