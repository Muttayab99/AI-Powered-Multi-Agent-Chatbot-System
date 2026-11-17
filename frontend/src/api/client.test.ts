import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '@/test/server'
import { api, ApiError } from './client'

describe('api client', () => {
  it('posts the query and session id to /api/chat', async () => {
    let body: unknown
    server.use(
      http.post('/api/chat', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ reply: 'Paris', agent: 'general', success: true, session_id: 's1' })
      }),
    )
    const result = await api.chat('s1', 'Capital of France?')
    expect(body).toEqual({ session_id: 's1', query: 'Capital of France?' })
    expect(result.reply).toBe('Paris')
  })

  it("surfaces FastAPI's detail message on errors", async () => {
    server.use(http.post('/api/upload', () => HttpResponse.json({ detail: 'File is larger than 50 MB.' }, { status: 413 })))
    const error = await api.upload('s1', new File(['x'], 'a.txt')).catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 413, message: 'File is larger than 50 MB.' })
  })

  it('reads the first validation message', async () => {
    server.use(
      http.post('/api/chat', () =>
        HttpResponse.json({ detail: [{ msg: 'String should have at least 1 character' }] }, { status: 422 }),
      ),
    )
    await expect(api.chat('s1', ' ')).rejects.toThrow('String should have at least 1 character')
  })

  it('explains when the server is unreachable', async () => {
    server.use(http.get('/api/health', () => HttpResponse.error()))
    await expect(api.health()).rejects.toMatchObject({ status: 0, message: expect.stringMatching(/Can't reach/) })
  })

  it('escapes session ids in the path', async () => {
    let path = ''
    server.use(
      http.delete('/api/sessions/:id', ({ request }) => {
        path = new URL(request.url).pathname
        return HttpResponse.json({ success: true })
      }),
    )
    await api.clearSession('a/b')
    expect(path).toBe('/api/sessions/a%2Fb')
  })
})
