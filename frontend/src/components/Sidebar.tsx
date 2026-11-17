import { FileTextIcon, GlobeIcon, Loader2Icon, MoonIcon, PlayIcon, PlusIcon, SunIcon, UploadIcon } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { cn } from 'cn'
import { useHealth, useSession } from '@/api/queries'
import { useChat } from '@/chat/ChatProvider'
import { UPLOAD_ACCEPT } from '@/lib/files'
import type { useTheme } from '@/lib/theme'
import { Tooltip, TooltipContent, TooltipTrigger } from './ui/tooltip'

interface SidebarProps {
  theme: ReturnType<typeof useTheme>
}

export function Sidebar({ theme }: SidebarProps) {
  const { reset, messages, pending } = useChat()

  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="flex items-center gap-2 px-1">
        <span className="size-2.5 rounded-full bg-primary shadow-[0_0_12px_var(--primary)]" aria-hidden />
        <span className="font-semibold tracking-tight">Multi-Agent Chat</span>
      </div>

      <button
        type="button"
        onClick={() => void reset()}
        disabled={pending || messages.length === 0}
        className="flex h-10 items-center justify-center gap-2 rounded-full border bg-card/60 text-sm font-medium shadow-sm transition-colors hover:bg-card focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-50"
      >
        <PlusIcon className="size-4" /> New chat
      </button>

      <ContextChips />
      <UploadDropzone />

      <div className="mt-auto flex items-center justify-between gap-2 px-1">
        <HealthDot />
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={theme.toggle}
              aria-label={`Switch to ${theme.resolved === 'dark' ? 'light' : 'dark'} theme`}
              className="grid size-9 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              {theme.resolved === 'dark' ? <SunIcon className="size-4" /> : <MoonIcon className="size-4" />}
            </button>
          </TooltipTrigger>
          <TooltipContent>{theme.resolved === 'dark' ? 'Light theme' : 'Dark theme'}</TooltipContent>
        </Tooltip>
      </div>
    </div>
  )
}

function ContextChips() {
  const { sessionId } = useChat()
  const session = useSession(sessionId).data
  const chips = [
    session?.video_title && { icon: PlayIcon, label: session.video_title, kind: 'Video', href: session.video_url },
    session?.document_name && { icon: FileTextIcon, label: session.document_name, kind: 'Document', href: null },
    (session?.page_title || session?.page_url) && {
      icon: GlobeIcon,
      label: session.page_title || session.page_url,
      kind: 'Web page',
      href: session.page_url,
    },
  ].filter(Boolean) as { icon: typeof PlayIcon; label: string; kind: string; href: string | null }[]

  return (
    <section aria-labelledby="context-heading" className="flex flex-col gap-2">
      <h2 id="context-heading" className="px-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        In this chat
      </h2>
      {chips.length === 0 ? (
        <p className="px-1 text-sm text-muted-foreground">
          Nothing loaded yet. Paste a YouTube or web link, or upload a file.
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {chips.map(({ icon: Icon, label, kind, href }) => (
            <li key={kind}>
              <a
                href={href ?? undefined}
                target="_blank"
                rel="noopener noreferrer"
                title={`${kind}: ${label}`}
                className={cn(
                  'flex items-center gap-2 rounded-full border bg-card/60 px-3 py-1.5 text-sm',
                  href ? 'hover:bg-card focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none' : 'pointer-events-none',
                )}
              >
                <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
                <span className="sr-only">{kind}: </span>
                <span className="truncate">{label}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function UploadDropzone() {
  const { upload, uploading } = useChat()
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) void upload(file)
  }

  return (
    <section aria-labelledby="upload-heading" className="flex flex-col gap-2">
      <h2 id="upload-heading" className="px-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Upload
      </h2>
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        disabled={!!uploading}
        className={cn(
          'flex flex-col items-center gap-1.5 rounded-xl border border-dashed px-3 py-5 text-center text-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
          dragging ? 'border-primary bg-primary/10' : 'hover:border-primary/50 hover:bg-card/50',
        )}
      >
        {uploading ? (
          <Loader2Icon className="size-5 animate-spin text-primary" />
        ) : (
          <UploadIcon className="size-5 text-muted-foreground" />
        )}
        <span className="font-medium">{uploading ? 'Reading the file…' : 'Drop a file or click'}</span>
        <span className="text-xs text-muted-foreground">PDF, DOCX, TXT, MD, CSV, JSON, HTML</span>
      </button>
      <input
        ref={input}
        type="file"
        accept={UPLOAD_ACCEPT}
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) void upload(file)
          event.target.value = ''
        }}
      />
    </section>
  )
}

function HealthDot() {
  const health = useHealth()
  const state = health.isError ? 'down' : health.data?.status === 'healthy' ? 'up' : health.data ? 'degraded' : 'checking'
  const label = {
    up: health.data?.llm.model ?? 'Connected',
    degraded: 'Some agents are down',
    down: 'Server unreachable',
    checking: 'Connecting…',
  }[state]
  const unhealthy = Object.entries(health.data?.agents ?? {})
    .filter(([, agent]) => agent.status !== 'healthy')
    .map(([name]) => name)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="flex min-w-0 items-center gap-2 rounded-md px-1 text-xs text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
          <span
            className={cn(
              'size-2 shrink-0 rounded-full',
              state === 'up' && 'bg-success',
              state === 'degraded' && 'bg-warning',
              state === 'down' && 'bg-destructive',
              state === 'checking' && 'animate-pulse bg-muted-foreground',
            )}
            aria-hidden
          />
          <span className="truncate">{label}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>
        {state === 'up' && `${health.data?.mode} mode, ${health.data?.llm.backend} backend`}
        {state === 'degraded' && `Unavailable: ${unhealthy.join(', ')}`}
        {state === 'down' && 'Start it with: python scripts/start_unified_server.py'}
        {state === 'checking' && 'Checking the server…'}
      </TooltipContent>
    </Tooltip>
  )
}
