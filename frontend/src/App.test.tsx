import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '@/test/server'
import App from './App'

describe('App', () => {
  it('shows example prompts before the first message', async () => {
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'What can I help with?' })).toBeInTheDocument()
    // Descriptions come from GET /api.
    expect(await screen.findByText('Runs Python code in a sandbox')).toBeInTheDocument()
  })

  it('sends with Enter and shows the reply with its agent', async () => {
    server.use(
      http.post('/api/chat', () =>
        HttpResponse.json({ reply: 'The answer is **5050**.', agent: 'python', success: true, session_id: 's' }),
      ),
    )
    const user = userEvent.setup()
    render(<App />)

    const input = screen.getByRole('textbox', { name: 'Message' })
    await user.type(input, 'sum 1 to 100{Enter}')

    const log = await screen.findByRole('log', { name: 'Conversation' })
    expect(within(log).getByText('sum 1 to 100')).toBeInTheDocument()
    // Rendered as markdown (bold) once the lazily loaded renderer arrives.
    expect(await within(log).findByText('5050', { selector: 'strong' }, { timeout: 5000 })).toBeInTheDocument()
    expect(within(log).getByText('Python')).toBeInTheDocument()
    expect(input).toHaveValue('')
  })

  it('keeps the message and offers Retry when the request fails', async () => {
    let calls = 0
    server.use(
      http.post('/api/chat', () => {
        calls += 1
        return calls === 1
          ? HttpResponse.error()
          : HttpResponse.json({ reply: 'Back online', agent: 'general', success: true, session_id: 's' })
      }),
    )
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByRole('textbox', { name: 'Message' }), 'hello{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent("Can't reach the chatbot server")
    await user.click(screen.getByRole('button', { name: /Retry/ }))
    expect(await screen.findByText('Back online')).toBeInTheDocument()
  })

  it('restores the conversation the server still has after a reload', async () => {
    localStorage.setItem('chatbot.session-id', 'saved')
    server.use(
      http.get('/api/sessions/saved', () =>
        HttpResponse.json({
          session_id: 'saved',
          video_url: null,
          video_title: null,
          document_name: 'report.pdf',
          page_url: null,
          page_title: null,
          last_agent: 'document',
          history: [
            { role: 'user', content: 'What is the budget?' },
            { role: 'assistant', content: 'It is 42 million.', agent: 'document' },
          ],
        }),
      ),
    )
    render(<App />)
    expect(await screen.findByText('It is 42 million.')).toBeInTheDocument()
    expect(screen.getAllByText('report.pdf').length).toBeGreaterThan(0)
  })

  it('rejects unsupported files before uploading', async () => {
    const user = userEvent.setup({ applyAccept: false })
    const { container } = render(<App />)
    const input = container.querySelector<HTMLInputElement>('input[type=file]')!
    await user.upload(input, new File(['MZ'], 'tool.exe'))
    expect(await screen.findByText(/tool.exe isn't supported/)).toBeInTheDocument()
  })

  it('reports a failed upload in the conversation', async () => {
    server.use(http.post('/api/upload', () => HttpResponse.json({ detail: 'Disk full' }, { status: 500 })))
    const user = userEvent.setup()
    const { container } = render(<App />)
    await user.upload(container.querySelector<HTMLInputElement>('input[type=file]')!, new File(['hello'], 'notes.txt'))
    expect(await screen.findByText("Couldn't upload notes.txt. Disk full")).toBeInTheDocument()
  })

  it('shows a banner while the server is down', async () => {
    server.use(http.get('/api/health', () => HttpResponse.error()))
    render(<App />)
    expect(await screen.findByText(/Can't reach the chatbot server/, {}, { timeout: 4000 })).toBeInTheDocument()
  })
})
