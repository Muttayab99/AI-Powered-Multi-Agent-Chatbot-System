import { AlertCircleIcon, CheckIcon, CopyIcon, RotateCcwIcon } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { cn } from 'cn'
import type { Message } from '@/chat/reducer'
import { useCopy } from '@/lib/useCopy'
import { agentMeta } from './agents'

// The markdown pipeline is the biggest part of the bundle and isn't needed until the first reply.
const Markdown = lazy(() => import('./Markdown'))

interface MessageBubbleProps {
  message: Message
  onRetry?: (id: string) => void
}

// Fade and rise 8px; reduced motion keeps only the fade.
const enter = 'animate-in fade-in slide-in-from-bottom-2 duration-200 ease-out motion-reduce:slide-in-from-bottom-0'

export function MessageBubble({ message, onRetry }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className={cn(enter, 'flex flex-col items-end gap-1.5')}>
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 whitespace-pre-wrap text-primary-foreground shadow-sm sm:max-w-[75%]">
          {message.content}
        </div>
        {message.error && (
          <div role="alert" className="flex items-center gap-2 text-sm text-destructive">
            <AlertCircleIcon className="size-4 shrink-0" />
            <span>{message.error}</span>
            {onRetry && (
              <button
                type="button"
                onClick={() => onRetry(message.id)}
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-medium underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <RotateCcwIcon className="size-3.5" /> Retry
              </button>
            )}
          </div>
        )}
      </div>
    )
  }
  return <AssistantMessage message={message} />
}

function AssistantMessage({ message }: { message: Message }) {
  const meta = agentMeta(message.agent)
  const Icon = meta.icon
  const { copied, copy } = useCopy()

  return (
    <article
      className={cn(
        enter,
        'group/msg rounded-2xl border bg-card px-4 py-3.5 text-card-foreground shadow-sm sm:px-5',
        message.failed && 'border-warning/40',
      )}
    >
      <header className="mb-2 flex items-center justify-between gap-2">
        <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1', meta.badge)}>
          <Icon className="size-3.5" aria-hidden />
          {meta.label}
        </span>
        <button
          type="button"
          onClick={() => copy(message.content)}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-muted-foreground opacity-100 transition-opacity hover:text-foreground focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:opacity-0 sm:group-hover/msg:opacity-100"
          aria-label={copied ? 'Copied' : 'Copy reply'}
        >
          {copied ? <CheckIcon className="size-3.5" /> : <CopyIcon className="size-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </header>
      <Suspense fallback={<p className="leading-relaxed whitespace-pre-wrap">{message.content}</p>}>
        <Markdown content={message.content} />
      </Suspense>
    </article>
  )
}
