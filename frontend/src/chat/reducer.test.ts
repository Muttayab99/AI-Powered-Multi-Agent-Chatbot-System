import { describe, expect, it } from 'vitest'
import { chatReducer, type ChatState } from './reducer'

const empty: ChatState = { sessionId: 's1', messages: [], pending: false }

describe('chatReducer', () => {
  it('hydrates server history only into an empty chat', () => {
    const history = [
      { role: 'user' as const, content: 'hi' },
      { role: 'assistant' as const, content: 'hello', agent: 'general' as const },
    ]
    const hydrated = chatReducer(empty, { type: 'hydrate', history })
    expect(hydrated.messages.map((m) => m.content)).toEqual(['hi', 'hello'])
    expect(chatReducer(hydrated, { type: 'hydrate', history: [{ role: 'user', content: 'other' }] })).toBe(hydrated)
  })

  it('marks a failed request on the user message and clears it on retry', () => {
    let state = chatReducer(empty, { type: 'send', id: 'u1', content: 'hi' })
    expect(state.pending).toBe(true)
    state = chatReducer(state, { type: 'fail', id: 'u1', error: 'offline' })
    expect(state).toMatchObject({ pending: false, messages: [{ id: 'u1', error: 'offline' }] })
    state = chatReducer(state, { type: 'retry', id: 'u1' })
    expect(state.pending).toBe(true)
    expect(state.messages[0].error).toBeUndefined()
  })

  it('appends replies with their agent and resets to a new session', () => {
    let state = chatReducer(empty, { type: 'send', id: 'u1', content: 'run code' })
    state = chatReducer(state, { type: 'reply', content: '6', agent: 'python', failed: false })
    expect(state.messages[1]).toMatchObject({ role: 'assistant', agent: 'python', content: '6' })
    expect(chatReducer(state, { type: 'reset', sessionId: 's2' })).toEqual({ sessionId: 's2', messages: [], pending: false })
  })
})
