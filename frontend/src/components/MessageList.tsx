import { useEffect, useRef } from 'react'
import { useChat } from '@/chat/ChatProvider'
import { EmptyState } from './EmptyState'
import { MessageBubble } from './MessageBubble'
import { ThinkingIndicator } from './ThinkingIndicator'

// Within this distance of the bottom counts as "following" the conversation.
const STICK_PX = 120

export function MessageList() {
  const { messages, pending, uploading, retry } = useChat()
  const scroller = useRef<HTMLDivElement>(null)
  const following = useRef(true)

  // Keep the newest message in view, unless the user scrolled up to read.
  useEffect(() => {
    const el = scroller.current
    if (el && following.current) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages.length, pending, uploading])

  const lastUser = messages.findLast((m) => m.role === 'user')

  return (
    <div
      ref={scroller}
      onScroll={(event) => {
        const el = event.currentTarget
        following.current = el.scrollHeight - el.scrollTop - el.clientHeight < STICK_PX
      }}
      className="flex-1 overflow-y-auto"
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 pt-6 pb-40 sm:px-6">
        {messages.length === 0 && !pending && !uploading ? (
          <EmptyState />
        ) : (
          <div role="log" aria-live="polite" aria-label="Conversation" className="flex flex-col gap-5">
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                // Only the latest unanswered message can be retried; earlier ones are history.
                onRetry={message.id === lastUser?.id ? retry : undefined}
              />
            ))}
            {pending && <ThinkingIndicator />}
            {uploading && <ThinkingIndicator label={`Reading ${uploading}…`} />}
          </div>
        )}
      </div>
    </div>
  )
}
