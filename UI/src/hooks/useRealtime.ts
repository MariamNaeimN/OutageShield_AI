import { useEffect, useRef, useCallback, useState } from 'react'
import { realtime, type WebSocketMessage } from '../services/websocket'

/**
 * Hook to connect to the real-time WebSocket and auto-disconnect on unmount.
 */
export function useRealtimeConnection() {
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    realtime.connect()

    const unsubConnect = realtime.on('connection', (msg) => {
      const payload = msg as unknown as { type: string }
      setConnected(payload.type === 'connected')
    })

    return () => {
      unsubConnect()
    }
  }, [])

  return connected
}

/**
 * Hook to subscribe to a specific message type.
 * Automatically cleans up on unmount.
 */
export function useRealtimeEvent(type: string, handler: (message: WebSocketMessage) => void) {
  const handlerRef = useRef(handler)
  handlerRef.current = handler

  useEffect(() => {
    const unsubscribe = realtime.on(type, (msg) => handlerRef.current(msg))
    return unsubscribe
  }, [type])
}

/**
 * Hook to subscribe to all updates for a specific incident.
 */
export function useIncidentStream(incidentId: string | undefined, handler: (message: WebSocketMessage) => void) {
  const handlerRef = useRef(handler)
  handlerRef.current = handler

  useEffect(() => {
    if (!incidentId) return
    const unsubscribe = realtime.onIncident(incidentId, (msg) => handlerRef.current(msg))
    return unsubscribe
  }, [incidentId])
}

/**
 * Hook that returns a state value that auto-updates from WebSocket.
 * Combines initial fetch with real-time updates.
 */
export function useRealtimeData<T>(
  fetchFn: () => Promise<T>,
  updateTypes: string[],
  transformUpdate?: (current: T, message: WebSocketMessage) => T
) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Initial fetch
  const refresh = useCallback(async () => {
    try {
      setError(null)
      const result = await fetchFn()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch')
    } finally {
      setLoading(false)
    }
  }, [fetchFn])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Real-time updates
  useEffect(() => {
    const unsubscribers = updateTypes.map(type =>
      realtime.on(type, (message) => {
        if (transformUpdate && data) {
          setData(transformUpdate(data, message))
        } else {
          // Default: refetch on any relevant update
          refresh()
        }
      })
    )

    return () => unsubscribers.forEach(unsub => unsub())
  }, [updateTypes, transformUpdate, data, refresh])

  return { data, loading, error, refresh }
}
