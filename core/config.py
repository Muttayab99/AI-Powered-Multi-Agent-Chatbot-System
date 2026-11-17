"""Central configuration, read from environment variables and an optional .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# LLM: Groq is used when a key is present, otherwise a small local model.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_ROUTER_MODEL = os.getenv("GROQ_ROUTER_MODEL", "openai/gpt-oss-20b")
GROQ_REASONING_EFFORT = os.getenv("GROQ_REASONING_EFFORT", "low")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
LOCAL_MAX_NEW_TOKENS = _int("LOCAL_MAX_NEW_TOKENS", 384)

# How much source text is sent to the LLM in one request.
GROQ_MAX_CONTEXT_CHARS = _int("GROQ_MAX_CONTEXT_CHARS", 12000)
LOCAL_MAX_CONTEXT_CHARS = _int("LOCAL_MAX_CONTEXT_CHARS", 5000)

# Retrieval
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHUNK_SIZE = _int("CHUNK_SIZE", 1000)
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 150)
RETRIEVAL_K = _int("RETRIEVAL_K", 5)

# Agents
MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 50)
FETCH_MAX_MB = _int("FETCH_MAX_MB", 5)
FETCH_TIMEOUT = _int("FETCH_TIMEOUT", 20)
ALLOW_PRIVATE_URLS = _bool("ALLOW_PRIVATE_URLS", False)
PYTHON_TIMEOUT = _int("PYTHON_TIMEOUT", 10)
PYTHON_MAX_OUTPUT = _int("PYTHON_MAX_OUTPUT", 20000)

# Servers
HOST = os.getenv("HOST", "127.0.0.1")
GATEWAY_PORT = _int("GATEWAY_PORT", 8000)
AGENT_PORTS = {
    "youtube": _int("YOUTUBE_PORT", 8001),
    "document": _int("DOCUMENT_PORT", 8002),
    "python": _int("PYTHON_PORT", 8003),
    "fetch": _int("FETCH_PORT", 8004),
}
AGENT_URLS = {
    name: os.getenv(f"{name.upper()}_AGENT_URL", f"http://127.0.0.1:{port}/mcp")
    for name, port in AGENT_PORTS.items()
}
AGENT_CALL_TIMEOUT = _int("AGENT_CALL_TIMEOUT", 600)

# Web frontend: the gateway serves the built app from here when it exists. Origins allowed to call the API
# from another port (the Vite dev server); comma-separated.
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", ROOT_DIR / "frontend" / "dist"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
