import { CheckIcon, CopyIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useCopy } from '@/lib/useCopy'

interface CodeBlockProps {
  code: string
  language?: string
}

/** Fenced code from a reply. Shiki (and each language grammar) is loaded only when code first appears. */
export function CodeBlock({ code, language }: CodeBlockProps) {
  const [html, setHtml] = useState<string | null>(null)
  const { copied, copy } = useCopy()

  useEffect(() => {
    let cancelled = false
    import('shiki')
      .then(({ codeToHtml }) =>
        codeToHtml(code, {
          lang: language || 'text',
          themes: { light: 'github-light', dark: 'github-dark' },
          defaultColor: false,
        }),
      )
      .then((result) => !cancelled && setHtml(result))
      // Unknown language: keep the plain rendering.
      .catch(() => !cancelled && setHtml(null))
    return () => {
      cancelled = true
    }
  }, [code, language])

  return (
    <div className="group/code relative my-3 overflow-hidden rounded-lg border bg-muted/60">
      <div className="flex items-center justify-between border-b px-3 py-1.5 text-xs text-muted-foreground">
        <span className="font-mono">{language || 'text'}</span>
        <button
          type="button"
          onClick={() => copy(code)}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          aria-label={copied ? 'Copied' : 'Copy code'}
        >
          {copied ? <CheckIcon className="size-3.5" /> : <CopyIcon className="size-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      {html ? (
        <div
          className="overflow-x-auto p-3 font-mono text-[13px] leading-relaxed [&_pre]:!bg-transparent"
          // Shiki escapes the code; the only markup is its own spans.
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre className="overflow-x-auto p-3 font-mono text-[13px] leading-relaxed">
          <code>{code}</code>
        </pre>
      )}
    </div>
  )
}
