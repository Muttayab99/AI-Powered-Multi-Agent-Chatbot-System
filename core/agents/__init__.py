"""Agent tool table: every agent's callable tools with their MCP descriptions.

The same functions are exposed as MCP tools by the agent servers and called in-process by the
unified gateway, so both deployment modes run identical code.
"""
from typing import Callable, Dict, Tuple

from core.agents import document, fetch, python_exec, youtube

AgentTools = Dict[str, Tuple[Callable, str]]

TOOLS: Dict[str, AgentTools] = {
    "youtube": {
        "query": (youtube.handle, "Answer a question about a YouTube video (summary if no question). Pass the video URL in video_url or inside the query; later calls in the same session reuse it."),
        "list_videos": (youtube.list_videos, "List videos whose transcripts are indexed."),
        "clear_session": (youtube.clear_session, "Forget the session's current video."),
        "health": (youtube.health, "Health check."),
    },
    "document": {
        "query": (document.handle, "Ask about, summarize, or get the sentiment of the document uploaded in this session."),
        "upload_document": (document.upload_document, "Upload a PDF/DOCX/TXT/MD file (base64) as the session's document."),
        "document_info": (document.info, "Describe the session's loaded document."),
        "clear_session": (document.clear_session, "Remove the session's document."),
        "health": (document.health, "Health check."),
    },
    "fetch": {
        "query": (fetch.handle, "Fetch a web page (URL in url or in the query) and summarize it or answer a question about it. Private/local addresses are refused."),
        "clear_session": (fetch.clear_session, "Forget the session's cached page."),
        "health": (fetch.health, "Health check."),
    },
    "python": {
        "query": (python_exec.handle, "Run Python code in a sandbox. Pass code directly in code, or a message containing it in query. Returns stdout/stderr."),
        "validate_code": (python_exec.validate, "Check whether code would be allowed by the sandbox, without running it."),
        "health": (python_exec.health, "Health check."),
    },
}
