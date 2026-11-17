import { BotIcon, CodeIcon, FileTextIcon, GlobeIcon, PlayIcon, type LucideIcon } from 'lucide-react'
import type { AgentName } from '@/api/types'

export interface AgentMeta {
  label: string
  icon: LucideIcon
  /** Tailwind text colour for the agent's icon. */
  text: string
  /** Tailwind classes for the small agent badge (text + tinted fill). */
  badge: string
  /** An example prompt shown on the empty state. */
  example: string
}

export const AGENTS: Record<AgentName, AgentMeta> = {
  youtube: {
    label: 'YouTube',
    icon: PlayIcon,
    text: 'text-agent-youtube',
    badge: 'text-agent-youtube bg-agent-youtube/12 ring-agent-youtube/25',
    example: 'Summarize https://www.youtube.com/watch?v=dQw4w9WgXcQ',
  },
  document: {
    label: 'Document',
    icon: FileTextIcon,
    text: 'text-agent-document',
    badge: 'text-agent-document bg-agent-document/12 ring-agent-document/25',
    example: 'What are the key points of the uploaded document?',
  },
  fetch: {
    label: 'Web',
    icon: GlobeIcon,
    text: 'text-agent-fetch',
    badge: 'text-agent-fetch bg-agent-fetch/12 ring-agent-fetch/25',
    example: 'Summarize https://en.wikipedia.org/wiki/Model_Context_Protocol',
  },
  python: {
    label: 'Python',
    icon: CodeIcon,
    text: 'text-agent-python',
    badge: 'text-agent-python bg-agent-python/12 ring-agent-python/25',
    example: 'Run this Python: print(sum(range(1, 101)))',
  },
  general: {
    label: 'General',
    icon: BotIcon,
    text: 'text-agent-general',
    badge: 'text-agent-general bg-agent-general/12 ring-agent-general/25',
    example: 'Explain retrieval-augmented generation in two sentences.',
  },
}

export const agentMeta = (agent?: string): AgentMeta => AGENTS[(agent as AgentName) ?? 'general'] ?? AGENTS.general
