"""In-memory conversation sessions kept by the gateway."""
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

MAX_HISTORY = 40


@dataclass
class Session:
    session_id: str
    created_at: float = field(default_factory=time.time)
    video_url: Optional[str] = None
    video_title: Optional[str] = None
    document_name: Optional[str] = None
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    last_agent: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    def add_turn(self, query: str, reply: str, agent: str) -> None:
        self.history.append({"role": "user", "content": query})
        self.history.append({"role": "assistant", "content": reply, "agent": agent})
        del self.history[:-MAX_HISTORY]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_sessions: Dict[str, Session] = {}
_lock = threading.Lock()


def get(session_id: str) -> Session:
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = Session(session_id)
        return _sessions[session_id]


def exists(session_id: str) -> bool:
    return session_id in _sessions


def delete(session_id: str) -> bool:
    with _lock:
        return _sessions.pop(session_id, None) is not None


def all_ids() -> List[str]:
    with _lock:
        return list(_sessions)
