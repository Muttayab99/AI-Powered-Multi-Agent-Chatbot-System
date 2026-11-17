// Shapes returned by the gateway's REST API (servers/gateway.py).

export type AgentName = 'youtube' | 'document' | 'fetch' | 'python' | 'general'

export interface ApiInfo {
  name: string
  mode: 'unified' | 'microservices'
  available_agents: AgentName[]
  agents: Record<AgentName, string>
  max_upload_mb: number
}

export interface ChatResponse {
  reply: string
  agent: AgentName
  success: boolean
  session_id: string
  route_reason?: string
}

export interface UploadResponse {
  reply: string
  success: boolean
  session_id: string
}

export interface HistoryTurn {
  role: 'user' | 'assistant'
  content: string
  agent?: AgentName
}

export interface SessionInfo {
  session_id: string
  video_url: string | null
  video_title: string | null
  document_name: string | null
  page_url: string | null
  page_title: string | null
  last_agent: AgentName | null
  history: HistoryTurn[]
}

export interface AgentHealth {
  status: 'healthy' | 'unhealthy'
  error?: string
}

export interface Health {
  status: 'healthy' | 'degraded'
  mode: 'unified' | 'microservices'
  llm: { backend: string; model: string }
  agents: Record<string, AgentHealth>
  active_sessions: number
}
