import { useEffect, useState } from 'react'

// Video indexing and document embedding can take a while; say so instead of looking frozen.
const SLOW_AFTER_MS = 8000

export function ThinkingIndicator({ label = 'Thinking…' }: { label?: string }) {
  const [slow, setSlow] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), SLOW_AFTER_MS)
    return () => window.clearTimeout(timer)
  }, [])

  return (
    <div role="status" className="flex items-center gap-3 px-1 text-sm text-muted-foreground">
      <span className="flex gap-1" aria-hidden>
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-1.5 animate-pulse rounded-full bg-current motion-reduce:animate-none"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
      <span>{slow ? `${label.replace(/…$/, '')}. This can take a minute the first time.` : label}</span>
    </div>
  )
}
