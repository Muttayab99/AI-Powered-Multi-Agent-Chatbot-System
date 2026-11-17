import { SparklesIcon } from 'lucide-react'
import type { AgentName } from '@/api/types'
import { useInfo } from '@/api/queries'
import { useChat } from '@/chat/ChatProvider'
import { AGENTS } from './agents'

const ORDER: AgentName[] = ['youtube', 'document', 'fetch', 'python']

export function EmptyState() {
  const { send } = useChat()
  const descriptions = useInfo().data?.agents

  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-8 py-10 text-center sm:py-16">
      <div className="flex flex-col items-center gap-3">
        <span className="glass grid size-12 place-items-center rounded-2xl text-primary">
          <SparklesIcon className="size-6" />
        </span>
        <h1 className="text-2xl font-semibold tracking-tight">What can I help with?</h1>
        <p className="max-w-md text-muted-foreground">
          Each message goes to the right agent automatically. Paste a link, attach a file, or just ask.
        </p>
      </div>
      {/* minmax(0,1fr) and min-w-0 let the long example URLs truncate instead of widening the page. */}
      <ul className="grid w-full grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[repeat(2,minmax(0,1fr))]">
        {ORDER.map((name) => {
          const agent = AGENTS[name]
          const Icon = agent.icon
          return (
            <li key={name} className="min-w-0">
              <button
                type="button"
                onClick={() => send(agent.example)}
                className="flex h-full w-full min-w-0 flex-col gap-1.5 rounded-2xl border bg-card p-4 text-left shadow-sm transition-colors hover:border-primary/40 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <span className="flex items-center gap-2 text-sm font-medium">
                  <Icon className={`size-4 ${agent.text}`} aria-hidden />
                  {agent.label}
                </span>
                <span className="text-sm text-muted-foreground">{descriptions?.[name] ?? agent.example}</span>
                <span className="mt-1 w-full truncate text-xs text-muted-foreground/80">“{agent.example}”</span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
