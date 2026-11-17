import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from './client'

export const keys = {
  info: ['info'] as const,
  health: ['health'] as const,
  session: (id: string) => ['session', id] as const,
}

export function useInfo() {
  return useQuery({ queryKey: keys.info, queryFn: api.info, staleTime: Infinity })
}

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: api.health, refetchInterval: 30_000, retry: 1 })
}

/** The server-side session; null when it doesn't exist yet (new chat, or the gateway restarted). */
export function useSession(sessionId: string) {
  return useQuery({
    queryKey: keys.session(sessionId),
    queryFn: async () => {
      try {
        return await api.session(sessionId)
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
  })
}
