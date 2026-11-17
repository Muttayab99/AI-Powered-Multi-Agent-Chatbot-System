"""Unified server: gateway + all agents in one process. REST on /, MCP on /mcp.

Run:  python -m servers.unified   (or python scripts/start_unified_server.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config  # noqa: E402
from servers.gateway import create_app  # noqa: E402

app = create_app("local")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.GATEWAY_PORT)
