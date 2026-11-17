import { isValidElement, memo, type ReactElement } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { CodeBlock } from './CodeBlock'

const components: Components = {
  // Fenced code arrives as <pre><code class="language-x">; render it as a highlighted block.
  pre({ children }) {
    if (isValidElement(children)) {
      const { className, children: code } = (children as ReactElement<{ className?: string; children?: unknown }>).props
      const language = /language-([\w+-]+)/.exec(className ?? '')?.[1]
      return <CodeBlock code={String(code ?? '').replace(/\n$/, '')} language={language} />
    }
    return <pre>{children}</pre>
  },
  a({ children, href }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    )
  },
}

/** Agent replies are markdown. Raw HTML in them is dropped, never rendered. */
export default memo(function Markdown({ content }: { content: string }) {
  return (
    <div className="prose-chat">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} skipHtml>
        {content}
      </ReactMarkdown>
    </div>
  )
})
