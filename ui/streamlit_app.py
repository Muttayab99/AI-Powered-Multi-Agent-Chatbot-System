"""Streamlit chat UI for the multi-agent chatbot. Talks to the gateway's REST API.

Run:  streamlit run ui/streamlit_app.py      (gateway must be running, default http://localhost:8000)
"""
import os
import uuid
from typing import Any, Dict

import requests
import streamlit as st

API_URL = os.getenv("CHATBOT_API_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 900

AGENT_BADGES = {
    "youtube": "🟥 YouTube",
    "document": "🟩 Document",
    "fetch": "🟦 Web fetch",
    "python": "🟨 Python",
    "general": "⚪ General",
    "system": "⚙️ System",
}
EXAMPLES = [
    "Summarize https://www.youtube.com/watch?v=aircAruvnKk",
    "Fetch and summarize https://en.wikipedia.org/wiki/Model_Context_Protocol",
    "Run this code:\n```python\nimport math\nprint([math.factorial(n) for n in range(10)])\n```",
    "What is retrieval-augmented generation?",
]

st.set_page_config(page_title="Multi-Agent Chatbot", page_icon="🤖", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.uploaded = set()


def api(method: str, path: str, **kwargs) -> Dict[str, Any]:
    try:
        response = requests.request(method, f"{API_URL}{path}", timeout=kwargs.pop("timeout", REQUEST_TIMEOUT), **kwargs)
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": f"Can't reach the chatbot server at {API_URL}. Is it running?"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "The server took too long to respond."}
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not response.ok:
        return {"success": False, "error": data.get("detail") or f"HTTP {response.status_code}"}
    return data


def add_message(role: str, content: str, agent: str = None) -> None:
    st.session_state.messages.append({"role": role, "content": content, "agent": agent})


def send(query: str) -> None:
    add_message("user", query)
    with st.spinner("Thinking... (first use of an agent can take a while to load models)"):
        result = api("POST", "/chat", json={"session_id": st.session_state.session_id, "query": query})
    if "error" in result:
        add_message("assistant", f"⚠️ {result['error']}", "system")
    else:
        add_message("assistant", result.get("reply", ""), result.get("agent"))


# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("🤖 Multi-Agent Chatbot")

    health = api("GET", "/health", timeout=30)
    if "error" in health:
        st.error(health["error"])
    else:
        llm_info = health.get("llm", {})
        st.success(f"Server online · {health.get('mode', '?')} mode")
        st.caption(f"LLM: {llm_info.get('backend')} · {llm_info.get('model')}")
        with st.expander("Agents", expanded=False):
            for name, status in health.get("agents", {}).items():
                ok = status.get("status") == "healthy"
                st.markdown(f"{'🟢' if ok else '🔴'} **{name}**" + ("" if ok else f" - {status.get('error', '')}"))

    st.divider()
    st.subheader("📄 Document")
    uploaded = st.file_uploader("PDF, DOCX, TXT or MD", type=["pdf", "docx", "txt", "md"])
    if uploaded is not None:
        key = (uploaded.name, uploaded.size)
        if key not in st.session_state.uploaded:
            with st.spinner(f"Indexing {uploaded.name}..."):
                result = api(
                    "POST", "/upload",
                    data={"session_id": st.session_state.session_id},
                    files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")},
                )
            st.session_state.uploaded.add(key)
            message = result.get("error") or result.get("reply", "")
            add_message("assistant", ("✅ " if result.get("success") else "⚠️ ") + message, "document")

    session = api("GET", f"/sessions/{st.session_state.session_id}", timeout=10)
    if "error" not in session:
        context = []
        if session.get("video_title"):
            context.append(f"🎬 {session['video_title']}")
        if session.get("document_name"):
            context.append(f"📄 {session['document_name']}")
        if session.get("page_title") or session.get("page_url"):
            context.append(f"🌐 {session.get('page_title') or session.get('page_url')}")
        if context:
            st.divider()
            st.subheader("In this chat")
            for line in context:
                st.markdown(line)

    st.divider()
    if st.button("🗑️ New chat", use_container_width=True):
        api("DELETE", f"/sessions/{st.session_state.session_id}", timeout=30)
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.uploaded = set()
        st.rerun()
    st.caption(f"Session `{st.session_state.session_id[:8]}`")

# ---------------- Main chat ----------------
st.title("Chat")
st.caption("Paste a YouTube link, a web page URL, Python code, or upload a document - I'll route it to the right agent.")

if not st.session_state.messages:
    st.markdown("**Try one of these:**")
    columns = st.columns(2)
    for i, example in enumerate(EXAMPLES):
        if columns[i % 2].button(example.splitlines()[0], key=f"example-{i}", use_container_width=True):
            send(example)
            st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="🧑" if message["role"] == "user" else "🤖"):
        if message.get("agent"):
            st.caption(AGENT_BADGES.get(message["agent"], message["agent"]))
        st.markdown(message["content"])

if prompt := st.chat_input("Ask anything... (Shift+Enter for a new line)"):
    send(prompt)
    st.rerun()
