# AI-Powered Multi-Agent Chatbot System

A chatbot that routes each message to a specialised agent, built on the **Model Context Protocol (MCP)**, LangChain, FAISS and Groq.

| Agent | What it does | How |
|---|---|---|
| **YouTube** | Summarizes videos and answers questions about them | Transcript via `youtube-transcript-api` (fallback: `yt-dlp` captions) → FAISS index → LLM |
| **Document** | Q&A, summaries and sentiment for uploaded PDF / DOCX / TXT / MD files | `pypdf` / `python-docx` → FAISS index → LLM |
| **Web fetch** | Reads a web page and summarizes it or answers questions about it | `requests` + BeautifulSoup, with SSRF protection |
| **Python** | Runs Python code and returns the output | AST validation + restricted runtime + isolated subprocess with timeout |
| **General** | Everything else (chat, general questions) | LLM |

The **router** picks the agent from clear signals first (a YouTube link, code, a URL, mentions of "the document"). Ambiguous follow-ups ("what about the conclusion?") go to the agent you were just talking to, or to a Groq classifier when a key is set. Each chat session remembers its video, document and page, so follow-up questions work.

## Architecture

```
 Web UI (React, served at :8000)   any MCP client (Claude, Cursor, ...)
        │ REST                         │ MCP (streamable HTTP)
        ▼                              ▼
 ┌───────────────────────────────────────────────┐
 │ Gateway :8000   REST /api/chat /upload /health│
 │                 MCP  /mcp/                    │
 │   intent router → orchestrator → sessions     │
 └───────────────┬───────────────────────────────┘
                 │ unified mode: in-process calls
                 │ microservices mode: MCP calls
     ┌───────────┼─────────────┬──────────────┐
     ▼           ▼             ▼              ▼
  YouTube     Document       Python         Fetch
  :8001/mcp   :8002/mcp      :8003/mcp      :8004/mcp
```

The agent logic lives once in `core/agents/`. The same functions are called in-process by the unified server and exposed as MCP tools by the agent servers, so both deployment modes behave identically.

## Setup

Requires **Python 3.11+**, and **Node.js 20+** for the web UI.

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1      Linux/macOS: source .venv/bin/activate

pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only torch, much smaller
pip install -r requirements.txt

cp .env.example .env    # then put your key in GROQ_API_KEY

cd frontend && npm install && npm run build && cd ..   # build the web UI once
```

**Groq API key:** get a free key at <https://console.groq.com/keys> and put it in `.env`. The default models are `openai/gpt-oss-120b` for answers and `openai/gpt-oss-20b` for routing and note-taking. You can change them in `.env`, using models listed at <https://console.groq.com/docs/models>. Without a key the system still works, but it falls back to a small local model (`Qwen2.5-0.5B-Instruct`, about 1 GB downloaded on first use). That model is slower and gives noticeably weaker answers.

The first time an agent indexes something, it also downloads the `all-MiniLM-L6-v2` embedding model (about 90 MB).

## Running

**Unified mode** (one process, recommended):

```bash
python scripts/start_unified_server.py
```

**Microservices mode** (four agent MCP servers plus the router):

```bash
python scripts/start_servers.py
```

Then open **http://localhost:8000**. The gateway serves the built web UI from `frontend/dist`.

While working on the UI, add `--web` to also start the Vite dev server with hot reload on **http://localhost:5173** (it proxies `/api` to the gateway). The old Streamlit UI still starts with `--ui` until it is removed.

| URL | What |
|---|---|
| http://localhost:8000 | Chat UI (after `npm run build`) |
| http://localhost:5173 | Chat UI dev server (`--web`) |
| http://localhost:8000/docs | REST API (Swagger) |
| http://localhost:8000/mcp/ | MCP endpoint (gateway) |
| http://localhost:800[1-4]/mcp | Agent MCP servers (microservices mode) |

## Usage examples

```
Summarize https://www.youtube.com/watch?v=aircAruvnKk
  → What does he say about gradient descent?

Fetch and summarize https://en.wikipedia.org/wiki/Model_Context_Protocol
  → Who created it?

(drop report.pdf on the sidebar, or use the paperclip)
  → What is the summary?   /   What is the sentiment?   /   What does it say about pricing?

Execute this Python code:
import math
print([math.factorial(n) for n in range(8)])
```

## REST API

Routes live under `/api` (the same routes at the root still work for older clients).

```bash
curl -X POST localhost:8000/api/chat -H "Content-Type: application/json" \
     -d '{"session_id": "demo", "query": "run this code: print(2**10)"}'

curl -X POST localhost:8000/api/upload -F session_id=demo -F file=@report.pdf

curl localhost:8000/api/health
curl localhost:8000/api/sessions/demo           # loaded context + history
curl -X DELETE localhost:8000/api/sessions/demo
```

Set `CORS_ORIGINS` (comma-separated) if a browser app on another origin calls the API; it defaults to the Vite dev server.

## Using it from an MCP client

`config/mcp_config.json` points a client at the gateway, which exposes these tools: `chat`, `route`, `upload_document`, `session_info`, `clear_session` and `health`. In unified mode it also exposes every agent tool directly, such as `python_query` and `youtube_query`. `config/mcp_config_agents.json` connects straight to the four agent servers instead (microservices mode only).

## Python sandbox

Code runs in a separate `python -I` process. The process gets a throwaway working directory, no environment secrets, and a 10-second timeout (`PYTHON_TIMEOUT`). Before the code runs, it is checked for:

- **Imports:** only safe standard-library modules are allowed (`math`, `statistics`, `random`, `collections`, `itertools`, `json`, `re`, `datetime`, ...).
- **Blocked builtins:** `open`, `eval`, `exec`, `__import__`, `input`, `globals` and similar are unavailable.
- **Attribute access:** dunder and private attributes are blocked, except `self._x` inside classes.

Imported modules are also wrapped so their private internals and unsafe submodules can't be reached. File, network and OS access are not available, and `input()` is not supported.

Memory is capped (1 GB) only on Linux/macOS. On Windows, the timeout is the only limit on a runaway process.

## Configuration

All settings are environment variables, optionally set in `.env`. See `.env.example` for the full list: models, ports, upload and fetch size limits, the sandbox timeout, and `ALLOW_PRIVATE_URLS`, which lets the fetch agent read intranet or localhost pages.

## Tests

```bash
pytest                                  # backend
cd frontend && npm test                 # web UI unit + component tests
cd frontend && npm run test:e2e         # web UI against a real gateway (build first)
```

The web UI's end-to-end tests run at desktop and phone sizes and include an axe accessibility check in light and dark themes. The backend tests cover routing, URL and video-ID parsing, file loaders, SSRF blocking, the sandbox (including escape attempts), and the gateway end-to-end with the LLM stubbed out.

## Limitations

- **State is in memory.** Sessions, uploaded documents and video indexes are lost when the server restarts.
- **YouTube may block transcripts.** YouTube sometimes rate-limits or blocks transcript requests from cloud or datacenter IPs. The agent reports this clearly when it happens. Videos without captions can't be processed.
- **Very long sources are sampled.** For summaries of very long sources, up to 4 evenly spaced parts are summarized and then combined; with the local model, up to 3.
- **Groq's free tier is rate-limited.** It limits tokens per minute, so summarizing several long pages or videos back to back can pause for 10–30 seconds while requests are retried automatically. A paid Groq tier removes this.
- **Some pages can't be read.** Pages that need JavaScript to render, or that require a login, can't be fetched.

## Project layout

```
core/
  config.py          settings (.env)
  llm.py             Groq / local model
  rag.py             chunking, FAISS, grounded answers, summaries
  intent.py          routing rules + LLM classifier
  orchestrator.py    routes, dispatches (local or MCP), updates sessions
  sessions.py        conversation state
  mcp_client.py      MCP client for microservices mode
  loaders.py         PDF/DOCX/TXT/HTML text extraction
  agents/            youtube, document, fetch, python_exec (+ sandbox_runner), general
servers/
  gateway.py         FastAPI REST + MCP endpoint
  unified.py         gateway with in-process agents
  router.py          gateway calling agent servers over MCP
  youtube.py document.py python.py fetch.py   agent MCP servers
scripts/             launchers
frontend/            web UI (React + Vite); see frontend/README.md
ui/streamlit_app.py  legacy chat UI, to be removed
tests/
```
