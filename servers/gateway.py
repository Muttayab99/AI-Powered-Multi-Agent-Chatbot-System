"""Gateway: REST API for the UI plus an MCP endpoint at /mcp, both backed by the orchestrator."""
import contextlib
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from core import config, intent, sessions
from core.agents import TOOLS
from core.orchestrator import AGENT_DESCRIPTIONS, Orchestrator
from servers.common import register_tools


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=50000)
    session_id: Optional[str] = None


def build_mcp(orchestrator: Orchestrator) -> MCPServer:
    mcp = MCPServer("multi-agent-chatbot")

    @mcp.tool()
    async def chat(session_id: str, query: str) -> Dict[str, Any]:
        """Send a message to the chatbot. It is routed to the right agent (YouTube, document, web fetch,
        Python, or general chat) and the agent's answer is returned. Reuse session_id for follow-ups."""
        return await orchestrator.chat(session_id, query)

    @mcp.tool()
    async def route(session_id: str, query: str) -> Dict[str, Any]:
        """Show which agent a message would be routed to, without running it."""
        s = sessions.get(session_id)
        ctx = intent.RouteContext(s.video_title, s.document_name, s.page_url, s.last_agent)
        decision = intent.detect(query, ctx)
        return {"agent": decision.agent, "reason": decision.reason}

    @mcp.tool()
    async def upload_document(session_id: str, filename: str, content_base64: str) -> Dict[str, Any]:
        """Upload a PDF/DOCX/TXT/MD file (base64-encoded) for the session; then ask about it with chat."""
        import base64

        return await orchestrator.upload(session_id, filename, base64.b64decode(content_base64))

    @mcp.tool()
    async def session_info(session_id: str) -> Dict[str, Any]:
        """Return the session's loaded video/document/page and its conversation history."""
        return sessions.get(session_id).to_dict()

    @mcp.tool()
    async def clear_session(session_id: str) -> Dict[str, Any]:
        """Delete a session and everything loaded in it."""
        return {"success": await orchestrator.clear_session(session_id)}

    @mcp.tool()
    async def health() -> Dict[str, Any]:
        """Health of the gateway and every agent."""
        return await orchestrator.health()

    if orchestrator.mode == "local":
        # The unified server also exposes each agent's tools directly, e.g. python_query, youtube_query.
        for agent, tools in TOOLS.items():
            register_tools(mcp, {k: v for k, v in tools.items() if k != "health"}, prefix=f"{agent}_")
    return mcp


def create_app(mode: str) -> FastAPI:
    orchestrator = Orchestrator(mode)
    mcp = build_mcp(orchestrator)
    # Mounted at /mcp below, so the MCP endpoint is /mcp/. The session manager only exists after
    # streamable_http_app() is called, and a mounted app's own lifespan doesn't run, so we run it here.
    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/", stateless_http=True, json_response=True, host=config.HOST
    )

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        async with mcp.session_manager.run():
            yield

    name = "Unified server" if mode == "local" else "Router (microservices)"
    app = FastAPI(title=f"Multi-Agent Chatbot - {name}", lifespan=lifespan)
    # The Vite dev server runs on another port; the built frontend is same-origin and doesn't need this.
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

    async def info() -> Dict[str, Any]:
        return {
            "name": "AI-Powered Multi-Agent Chatbot",
            "mode": "unified" if mode == "local" else "microservices",
            "available_agents": list(AGENT_DESCRIPTIONS),
            "agents": AGENT_DESCRIPTIONS,
            "max_upload_mb": config.MAX_UPLOAD_MB,
            "endpoints": {"chat": "POST /api/chat", "upload": "POST /api/upload", "health": "GET /api/health",
                          "session": "GET|DELETE /api/sessions/{id}", "mcp": "/mcp", "docs": "/docs"},
        }

    api = APIRouter()

    @api.get("/health")
    async def health() -> Dict[str, Any]:
        return await orchestrator.health()

    @api.post("/chat")
    async def chat(request: ChatRequest) -> Dict[str, Any]:
        query = request.query.strip()
        if not query:
            raise HTTPException(400, "query is empty")
        return await orchestrator.chat(request.session_id or str(uuid.uuid4()), query)

    @api.post("/upload")
    async def upload(file: UploadFile = File(...), session_id: str = Form(...)) -> Dict[str, Any]:
        data = await file.read(config.MAX_UPLOAD_MB * 1024 * 1024 + 1)
        if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"File is larger than {config.MAX_UPLOAD_MB} MB.")
        return await orchestrator.upload(session_id, file.filename or "upload.txt", data)

    @api.get("/sessions/{session_id}")
    async def get_session(session_id: str) -> Dict[str, Any]:
        if not sessions.exists(session_id):
            raise HTTPException(404, "session not found")
        return sessions.get(session_id).to_dict()

    @api.delete("/sessions/{session_id}")
    async def delete_session(session_id: str) -> Dict[str, Any]:
        return {"success": await orchestrator.clear_session(session_id)}

    app.add_api_route("/api", info, methods=["GET"])
    app.include_router(api, prefix="/api")
    # Legacy root paths, still used by the Streamlit UI.
    app.include_router(api, include_in_schema=False)
    app.mount("/mcp", mcp_app)

    # Mounted last so the API, /mcp and /docs take precedence over the frontend's files.
    if (config.FRONTEND_DIST / "index.html").is_file():
        app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="frontend")
    else:
        app.add_api_route("/", info, methods=["GET"], include_in_schema=False)
    return app
