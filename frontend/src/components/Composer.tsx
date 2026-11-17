import { ArrowUpIcon, Loader2Icon, PaperclipIcon } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useChat } from '@/chat/ChatProvider'
import { UPLOAD_ACCEPT } from '@/lib/files'
import { Tooltip, TooltipContent, TooltipTrigger } from './ui/tooltip'

export function Composer() {
  const { send, upload, pending, uploading } = useChat()
  const [text, setText] = useState('')
  const textarea = useRef<HTMLTextAreaElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  // "/" focuses the composer from anywhere except another text field.
  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      const target = event.target as HTMLElement
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return
      if (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
      event.preventDefault()
      textarea.current?.focus()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Refocus once a reply arrives so the user can keep typing.
  useEffect(() => {
    if (!pending) textarea.current?.focus()
  }, [pending])

  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    if (!text.trim() || pending) return
    send(text)
    setText('')
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form onSubmit={submit} className="glass flex items-end gap-2 rounded-2xl p-2 pl-4">
      <label htmlFor="composer" className="sr-only">
        Message
      </label>
      <textarea
        id="composer"
        ref={textarea}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
        rows={1}
        placeholder="Ask anything, paste a YouTube or web link, or attach a file…"
        className="max-h-48 min-h-10 flex-1 resize-none [field-sizing:content] bg-transparent py-2 text-[15px] leading-6 placeholder:text-muted-foreground focus:outline-none"
      />
      <input
        ref={fileInput}
        type="file"
        accept={UPLOAD_ACCEPT}
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) void upload(file)
          event.target.value = ''
        }}
      />
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            disabled={!!uploading}
            aria-label="Attach a document"
            className="grid size-10 shrink-0 place-items-center rounded-xl text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-50"
          >
            {uploading ? <Loader2Icon className="size-5 animate-spin" /> : <PaperclipIcon className="size-5" />}
          </button>
        </TooltipTrigger>
        <TooltipContent>Attach PDF, DOCX, TXT, MD, CSV, JSON or HTML</TooltipContent>
      </Tooltip>
      <button
        type="submit"
        disabled={!text.trim() || pending}
        aria-label="Send message"
        className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm transition-[opacity,transform] hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none active:scale-95 disabled:opacity-40"
      >
        {pending ? <Loader2Icon className="size-5 animate-spin" /> : <ArrowUpIcon className="size-5" />}
      </button>
    </form>
  )
}
