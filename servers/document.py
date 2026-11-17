"""Document agent MCP server (microservices mode). Run: python -m servers.document"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from servers.common import run_agent_server  # noqa: E402

if __name__ == "__main__":
    run_agent_server("document")
