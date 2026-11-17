"""Router (microservices mode): gateway that forwards each message to the agent MCP servers.

Start the agent servers first (python scripts/start_servers.py does everything).
Run:  python -m servers.router
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config  # noqa: E402
from servers.gateway import create_app  # noqa: E402

app = create_app("remote")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.GATEWAY_PORT)
