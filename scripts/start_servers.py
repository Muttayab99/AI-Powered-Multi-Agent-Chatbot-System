#!/usr/bin/env python3
"""Microservices mode: start the four agent MCP servers, then the router gateway in front of them.

    python scripts/start_servers.py           # agents on 8001-8004, router on 8000
    python scripts/start_servers.py --web     # also start the React web UI on 5173 (after npm run build, :8000 serves it too)
    python scripts/start_servers.py --ui      # also start the legacy Streamlit UI on 8501
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config  # noqa: E402
from scripts._process import ProcessGroup, port_in_use, start_web_dev  # noqa: E402

AGENT_MODULES = {"youtube": "servers.youtube", "document": "servers.document",
                 "python": "servers.python", "fetch": "servers.fetch"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ui", action="store_true", help="also start the Streamlit UI (legacy)")
    parser.add_argument("--web", action="store_true", help="also start the React web UI dev server on 5173")
    args = parser.parse_args()

    ports = [*config.AGENT_PORTS.values(), config.GATEWAY_PORT]
    busy = [p for p in ports if port_in_use(p)]
    if busy:
        print(f"Ports already in use: {busy}. Stop whatever is using them first.")
        return 1
    if not config.GROQ_API_KEY:
        print("Note: GROQ_API_KEY is not set - using the local fallback model (slower, lower quality).")

    group = ProcessGroup()
    try:
        for agent, module in AGENT_MODULES.items():
            group.start(agent, [sys.executable, "-m", module])
        for agent in AGENT_MODULES:
            if not group.wait_for_port(agent, config.AGENT_PORTS[agent]):
                return 1
            print(f"OK {agent} agent: {config.AGENT_URLS[agent]}")

        group.start("router", [sys.executable, "-m", "servers.router"])
        if not group.wait_for_port("router", config.GATEWAY_PORT):
            return 1
        print(f"OK router: http://localhost:{config.GATEWAY_PORT}  (REST docs /docs, MCP /mcp/)")

        if args.web and not start_web_dev(group):
            return 1
        if args.ui:
            group.start("ui", [sys.executable, "-m", "streamlit", "run", "ui/streamlit_app.py",
                               "--server.headless", "true"])
            if group.wait_for_port("ui", 8501, timeout=60):
                print("OK UI: http://localhost:8501")
        print("All services running. Press Ctrl+C to stop.")
        group.wait()
    finally:
        group.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
