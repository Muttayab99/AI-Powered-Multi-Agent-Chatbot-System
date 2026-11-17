"""Orchestrator: routes each message to an agent and runs it, either in-process or over MCP.

mode="local"  - agents run inside this process (unified server).
mode="remote" - agents are separate MCP servers (microservices); calls go through core.mcp_client.
"""
import base64
import functools
import logging
from typing import Any, Dict

import anyio

from core import config, intent, llm, sessions
from core.agents import TOOLS, document, general

logger = logging.getLogger(__name__)

AGENT_DESCRIPTIONS = {
    "youtube": "Q&A and summaries for YouTube videos (paste a link)",
    "document": "Q&A, summaries and sentiment for uploaded PDF/DOCX/TXT files",
    "fetch": "Reads web pages and summarizes them or answers questions (paste a URL)",
    "python": "Runs Python code in a sandbox",
    "general": "General conversation",
}


class Orchestrator:
    def __init__(self, mode: str = "local"):
        if mode not in ("local", "remote"):
            raise ValueError("mode must be 'local' or 'remote'")
        self.mode = mode

    async def call(self, agent: str, tool: str, timeout: float = config.AGENT_CALL_TIMEOUT, **kwargs) -> Dict[str, Any]:
        if self.mode == "local":
            fn = TOOLS[agent][tool][0]
            return await anyio.to_thread.run_sync(functools.partial(fn, **kwargs))
        from core.mcp_client import call_tool

        return await call_tool(config.AGENT_URLS[agent], tool, kwargs, timeout)

    async def chat(self, session_id: str, query: str) -> Dict[str, Any]:
        session = sessions.get(session_id)
        context = intent.RouteContext(
            video_title=session.video_title,
            document_name=session.document_name,
            page_url=session.page_url,
            last_agent=session.last_agent,
        )
        decision = await anyio.to_thread.run_sync(intent.detect, query, context)
        agent = decision.agent
        history = [{"role": t["role"], "content": t["content"]} for t in session.history[-8:]]
        logger.info("session=%s agent=%s (%s)", session_id[:8], agent, decision.reason)

        try:
            if agent == "general":
                result = await anyio.to_thread.run_sync(general.handle, session_id, query, history)
            elif agent == "python":
                result = await self.call(agent, "query", session_id=session_id, query=query)
            elif agent == "youtube":
                result = await self.call(agent, "query", session_id=session_id, query=query,
                                         video_url=session.video_url, history=history)
            elif agent == "fetch":
                result = await self.call(agent, "query", session_id=session_id, query=query,
                                         url=session.page_url, history=history)
            else:
                result = await self.call(agent, "query", session_id=session_id, query=query, history=history)
        except llm.LLMError as e:
            result = {"success": False, "reply": f"The language model request failed: {e}"}
        except Exception as e:
            logger.exception("Agent %s failed", agent)
            result = {"success": False, "reply": f"The {agent} agent hit an error: {e}"}

        reply = result.get("reply") or "(no reply)"
        if result.get("success"):
            session.last_agent = agent
            if result.get("video_url"):
                session.video_url, session.video_title = result["video_url"], result.get("video_title")
            if result.get("url"):
                session.page_url, session.page_title = result["url"], result.get("page_title")
        session.add_turn(query, reply, agent)
        return {
            **result,
            "reply": reply,
            "agent": agent,
            "success": bool(result.get("success")),
            "session_id": session_id,
            "route_reason": decision.reason,
        }

    async def upload(self, session_id: str, filename: str, data: bytes) -> Dict[str, Any]:
        session = sessions.get(session_id)
        try:
            if self.mode == "local":
                result = await anyio.to_thread.run_sync(document.ingest, session_id, filename, data)
            else:
                result = await self.call("document", "upload_document", session_id=session_id, filename=filename,
                                         content_base64=base64.b64encode(data).decode("ascii"))
        except Exception as e:
            logger.exception("Upload failed")
            result = {"success": False, "reply": f"Upload failed: {e}"}
        if result.get("success"):
            session.document_name = filename
            session.last_agent = "document"
        return {**result, "session_id": session_id}

    async def clear_session(self, session_id: str) -> bool:
        for agent, tools in TOOLS.items():
            if "clear_session" in tools:
                try:
                    await self.call(agent, "clear_session", timeout=15, session_id=session_id)
                except Exception as e:
                    logger.warning("Couldn't clear %s state for %s: %s", agent, session_id, e)
        return sessions.delete(session_id)

    async def health(self) -> Dict[str, Any]:
        agents = {}
        for agent in TOOLS:
            try:
                with anyio.fail_after(10):
                    agents[agent] = await self.call(agent, "health", timeout=10)
            except Exception as e:
                agents[agent] = {"status": "unhealthy", "error": str(e)}
        healthy = all(a.get("status") == "healthy" for a in agents.values())
        return {
            "status": "healthy" if healthy else "degraded",
            "mode": "unified" if self.mode == "local" else "microservices",
            "llm": {"backend": llm.backend(), "model": llm.model_name()},
            "agents": agents,
            "active_sessions": len(sessions.all_ids()),
        }
