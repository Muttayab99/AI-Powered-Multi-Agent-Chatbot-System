import type { AgentName, HistoryTurn } from '@/api/types'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  agent?: AgentName
  /** Assistant replies where the agent couldn't do what was asked (e.g. no document loaded). */
  failed?: boolean
  /** User messages whose request never got an answer (network error, timeout). */
  error?: string
}

export interface ChatState {
  sessionId: string
  messages: Message[]
  pending: boolean
}

export type ChatAction =
  | { type: 'hydrate'; history: HistoryTurn[] }
  | { type: 'send'; id: string; content: string }
  | { type: 'retry'; id: string }
  | { type: 'reply'; content: string; agent: AgentName; failed: boolean }
  | { type: 'fail'; id: string; error: string }
  | { type: 'notice'; content: string; failed: boolean }
  | { type: 'reset'; sessionId: string }

let counter = 0
export const nextId = () => `m${Date.now().toString(36)}${(counter++).toString(36)}`

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'hydrate':
      // Only fill an empty chat: never overwrite messages the user already sees.
      if (state.messages.length) return state
      return {
        ...state,
        messages: action.history.map((turn) => ({ id: nextId(), role: turn.role, content: turn.content, agent: turn.agent })),
      }
    case 'send':
      return {
        ...state,
        pending: true,
        messages: [...state.messages, { id: action.id, role: 'user', content: action.content }],
      }
    case 'retry':
      return {
        ...state,
        pending: true,
        messages: state.messages.map((m) => (m.id === action.id ? { ...m, error: undefined } : m)),
      }
    case 'reply':
      return {
        ...state,
        pending: false,
        messages: [
          ...state.messages,
          { id: nextId(), role: 'assistant', content: action.content, agent: action.agent, failed: action.failed },
        ],
      }
    case 'fail':
      return {
        ...state,
        pending: false,
        messages: state.messages.map((m) => (m.id === action.id ? { ...m, error: action.error } : m)),
      }
    case 'notice':
      return {
        ...state,
        messages: [
          ...state.messages,
          { id: nextId(), role: 'assistant', content: action.content, agent: 'document', failed: action.failed },
        ],
      }
    case 'reset':
      return { sessionId: action.sessionId, messages: [], pending: false }
  }
}
