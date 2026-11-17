import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ApiInfo, Health } from '@/api/types'

export const info: ApiInfo = {
  name: 'AI-Powered Multi-Agent Chatbot',
  mode: 'unified',
  available_agents: ['youtube', 'document', 'fetch', 'python', 'general'],
  agents: {
    youtube: 'Q&A and summaries for YouTube videos (paste a link)',
    document: 'Q&A, summaries and sentiment for uploaded PDF/DOCX/TXT files',
    fetch: 'Reads web pages and summarizes them or answers questions (paste a URL)',
    python: 'Runs Python code in a sandbox',
    general: 'General conversation',
  },
  max_upload_mb: 1,
}

export const health: Health = {
  status: 'healthy',
  mode: 'unified',
  llm: { backend: 'groq', model: 'openai/gpt-oss-120b' },
  agents: { python: { status: 'healthy' } },
  active_sessions: 0,
}

// Default handlers: a healthy gateway with a brand-new session.
export const server = setupServer(
  http.get('/api', () => HttpResponse.json(info)),
  http.get('/api/health', () => HttpResponse.json(health)),
  http.get('/api/sessions/:id', () => HttpResponse.json({ detail: 'session not found' }, { status: 404 })),
)
