import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { api, ApiError } from '@/api/client'
import { keys, useInfo, useSession } from '@/api/queries'
import { checkUpload } from '@/lib/files'
import { loadSessionId, newSessionId } from '@/lib/session'
import { chatReducer, nextId, type ChatState } from './reducer'

interface ChatContextValue extends ChatState {
  /** Name of the file being uploaded, if any. */
  uploading: string | null
  send: (text: string) => void
  retry: (messageId: string) => void
  upload: (file: File) => Promise<void>
  reset: () => Promise<void>
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function ChatProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [state, dispatch] = useReducer(chatReducer, undefined, () => ({
    sessionId: loadSessionId(),
    messages: [],
    pending: false,
  }))
  const { sessionId } = state
  const session = useSession(sessionId)
  const maxUploadMb = useInfo().data?.max_upload_mb ?? 50
  const [uploading, setUploading] = useState<string | null>(null)

  // After a reload, show the conversation the server still holds for this session.
  useEffect(() => {
    if (session.data?.history.length) dispatch({ type: 'hydrate', history: session.data.history })
  }, [session.data])

  const refreshSession = useCallback(
    () => queryClient.invalidateQueries({ queryKey: keys.session(sessionId) }),
    [queryClient, sessionId],
  )

  const ask = useCallback(
    async (messageId: string, text: string) => {
      try {
        const result = await api.chat(sessionId, text)
        dispatch({ type: 'reply', content: result.reply, agent: result.agent, failed: !result.success })
        void refreshSession()
      } catch (error) {
        dispatch({ type: 'fail', id: messageId, error: error instanceof Error ? error.message : String(error) })
      }
    },
    [sessionId, refreshSession],
  )

  const send = useCallback(
    (text: string) => {
      const query = text.trim()
      if (!query || state.pending) return
      const id = nextId()
      dispatch({ type: 'send', id, content: query })
      void ask(id, query)
    },
    [ask, state.pending],
  )

  const retry = useCallback(
    (messageId: string) => {
      const message = state.messages.find((m) => m.id === messageId)
      if (!message || state.pending) return
      dispatch({ type: 'retry', id: messageId })
      void ask(messageId, message.content)
    },
    [ask, state.messages, state.pending],
  )

  const upload = useCallback(
    async (file: File) => {
      const problem = checkUpload(file, maxUploadMb)
      if (problem) {
        toast.error(problem)
        return
      }
      setUploading(file.name)
      try {
        const result = await api.upload(sessionId, file)
        // The document agent's reply ("Loaded 'x.pdf' (…)" or why it couldn't) goes into the chat.
        dispatch({ type: 'notice', content: result.reply, failed: !result.success })
        void refreshSession()
      } catch (error) {
        const message = error instanceof ApiError ? error.message : 'Upload failed.'
        dispatch({ type: 'notice', content: `Couldn't upload ${file.name}. ${message}`, failed: true })
      } finally {
        setUploading(null)
      }
    },
    [sessionId, refreshSession, maxUploadMb],
  )

  const reset = useCallback(async () => {
    try {
      await api.clearSession(sessionId)
    } catch {
      // The old session is abandoned either way; the server drops it when it restarts.
    }
    queryClient.removeQueries({ queryKey: keys.session(sessionId) })
    dispatch({ type: 'reset', sessionId: newSessionId() })
  }, [queryClient, sessionId])

  const value = useMemo(
    () => ({ ...state, uploading, send, retry, upload, reset }),
    [state, uploading, send, retry, upload, reset],
  )
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

export function useChat(): ChatContextValue {
  const context = useContext(ChatContext)
  if (!context) throw new Error('useChat must be used inside <ChatProvider>')
  return context
}
