"""Minimal MCP client used by the router to call agent servers over streamable HTTP."""
import json
from typing import Any, Dict

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client


class AgentCallError(RuntimeError):
    pass


async def call_tool(url: str, tool: str, arguments: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    try:
        http_client = create_mcp_http_client(timeout=httpx2.Timeout(30, read=timeout))
        async with http_client, streamable_http_client(url, http_client=http_client) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timeout) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments, read_timeout_seconds=timeout)
    except Exception as e:
        # anyio wraps failures in ExceptionGroups; surface the innermost cause.
        while isinstance(e, BaseExceptionGroup) and e.exceptions:
            e = e.exceptions[0]
        raise AgentCallError(f"{url} -> {tool}: {type(e).__name__}: {e}") from e

    text = "".join(getattr(block, "text", "") for block in getattr(result, "content", None) or [])
    if getattr(result, "is_error", None) or getattr(result, "isError", None):
        raise AgentCallError(text or f"tool '{tool}' failed")
    structured = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        if set(structured) == {"result"} and isinstance(structured["result"], dict):
            return structured["result"]
        return structured
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"success": True, "reply": text}
