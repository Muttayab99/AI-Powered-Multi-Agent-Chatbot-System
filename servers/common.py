"""Helpers shared by the MCP servers."""
import functools
import logging
from typing import Callable

import anyio
from mcp.server.mcpserver import MCPServer

from core import config
from core.agents import TOOLS, AgentTools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def threaded_tool(fn: Callable) -> Callable:
    """Wrap a blocking agent function as an async tool so slow calls don't block the server's event loop.

    functools.wraps keeps the original signature, which MCPServer uses for the tool's input schema.
    """

    @functools.wraps(fn)
    async def tool(**kwargs):
        return await anyio.to_thread.run_sync(functools.partial(fn, **kwargs))

    return tool


def register_tools(mcp: MCPServer, tools: AgentTools, prefix: str = "") -> None:
    for name, (fn, description) in tools.items():
        mcp.add_tool(threaded_tool(fn), name=f"{prefix}{name}", description=description)


def create_agent_server(agent: str) -> MCPServer:
    mcp = MCPServer(f"{agent}-agent")
    register_tools(mcp, TOOLS[agent])
    return mcp


def run_agent_server(agent: str) -> None:
    logging.getLogger(__name__).info(
        "Starting %s agent MCP server on http://%s:%s/mcp", agent, config.HOST, config.AGENT_PORTS[agent]
    )
    create_agent_server(agent).run(
        transport="streamable-http",
        host=config.HOST,
        port=config.AGENT_PORTS[agent],
        stateless_http=True,
        json_response=True,
    )
