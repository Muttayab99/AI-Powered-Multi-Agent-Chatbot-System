#!/usr/bin/env python3
"""Unified mode: one process serving the REST API, the MCP endpoint and all agents.

    python scripts/start_unified_server.py          # server on 8000
    python scripts/start_unified_server.py --web    # also start the React web UI on 5173 (after npm run build, :8000 serves it too)
    python scripts/start_unified_server.py --ui     # also start the legacy Streamlit UI on 8501
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config  # noqa: E402
from scripts._process import ProcessGroup, port_in_use, start_web_dev  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ui", action="store_true", help="also start the Streamlit UI (legacy)")
    parser.add_argument("--web", action="store_true", help="also start the React web UI dev server on 5173")
    args = parser.parse_args()

    if port_in_use(config.GATEWAY_PORT):
        print(f"Port {config.GATEWAY_PORT} is already in use. Stop whatever is using it first.")
        return 1
    if not config.GROQ_API_KEY:
        print("Note: GROQ_API_KEY is not set - using the local fallback model (slower, lower quality).")

    group = ProcessGroup()
    try:
        group.start("server", [sys.executable, "-m", "servers.unified"])
        if not group.wait_for_port("server", config.GATEWAY_PORT):
            return 1
        print(f"OK unified server: http://localhost:{config.GATEWAY_PORT}  (REST docs /docs, MCP /mcp/)")
        if args.web and not start_web_dev(group):
            return 1
        if args.ui:
            group.start("ui", [sys.executable, "-m", "streamlit", "run", "ui/streamlit_app.py",
                               "--server.headless", "true"])
            if group.wait_for_port("ui", 8501, timeout=60):
                print("OK UI: http://localhost:8501")
        print("Running. Press Ctrl+C to stop.")
        group.wait()
    finally:
        group.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
