"""General agent: plain conversation for anything that isn't about a video, document, page or code run."""
from typing import Any, Dict, List, Optional

from core import llm, rag

AGENT = "general"

SYSTEM_PROMPT = (
    "You are a helpful assistant inside a multi-agent chatbot. Besides chatting, the system can: "
    "answer questions about YouTube videos (the user pastes a link), answer questions about uploaded "
    "documents (PDF/DOCX/TXT, uploaded from the sidebar), read and summarize web pages (the user pastes a URL), "
    "and run Python code (the user asks to run code or pastes it in a ``` block). "
    "If the user seems to want one of those, briefly tell them how to trigger it. Answer concisely."
)


def handle(session_id: str, query: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *rag.history_messages(history), {"role": "user", "content": query}]
    return {"success": True, "agent": AGENT, "reply": llm.chat(messages, max_tokens=800, temperature=0.4)}
