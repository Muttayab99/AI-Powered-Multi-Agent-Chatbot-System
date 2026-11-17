# Multi-Agent Chat UI

React + TypeScript frontend for the multi-agent chatbot gateway (`servers/gateway.py`). Glass sidebar and
composer, light and dark themes, works from phone to desktop.

```bash
npm install
npm run dev        # http://localhost:5173, proxies /api to the gateway on :8000
npm run build      # writes dist/, which the gateway serves at http://localhost:8000
```

Start the gateway first: `python scripts/start_unified_server.py` from the repo root
(or `--web` to start both).

| Script | What it does |
| --- | --- |
| `npm run test` | Vitest unit and component tests (API mocked with MSW) |
| `npm run typecheck` / `npm run lint` | TypeScript and oxlint |
| `npm run test:e2e` | Playwright against a real gateway on port 8010 (build first; needs `npx playwright install chromium` once) |

Layout: `src/api` (typed client + TanStack Query hooks), `src/chat` (conversation state),
`src/components` (UI; `ui/` holds shadcn/ui primitives), `src/index.css` (design tokens and glass styles).
