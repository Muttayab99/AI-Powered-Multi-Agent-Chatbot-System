import streamlit as st
import requests
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import time

# Configure page
st.set_page_config(
    page_title="MCP Orchestrator",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
ROUTER_BASE_URL = "http://localhost:9000"
DOCUMENT_BOT_URL = "http://localhost:8002"

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "available_agents" not in st.session_state:
    st.session_state.available_agents = []
if "health_data" not in st.session_state:
    st.session_state.health_data = {"error": "Not checked"}
if "document_uploaded" not in st.session_state:
    st.session_state.document_uploaded = False

@st.cache_data(ttl=60)
def fetch_available_agents():
    try:
        response = requests.get(f"{ROUTER_BASE_URL}/", timeout=2)
        if response.status_code == 200:
            return response.json()["available_agents"]
        return []
    except:
        return []

@st.cache_data(ttl=60)
def check_health() -> Dict[str, Any]:
    try:
        response = requests.get(f"{ROUTER_BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            return response.json()
        return {"error": f"HTTP Error {response.status_code}"}
    except:
        return {"error": "Cannot connect to router service."}

def make_request(endpoint: str, data: Dict[str, Any] = None, files: Optional[Dict] = None) -> Dict[str, Any]:
    try:
        url = f"{ROUTER_BASE_URL}{endpoint}"
        response = requests.post(url, json=data, files=files, timeout=3000)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to router service."}
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP Error {e.response.status_code}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def upload_document(file, session_id: str) -> Dict[str, Any]:
    url = f"{DOCUMENT_BOT_URL}/upload"
    data = {"session_id": session_id}
    files = {"file": (file.name, file.getvalue(), file.type)}
    try:
        response = requests.post(url, data=data, files=files, timeout=3000)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to document bot service."}
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP Error {e.response.status_code}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def add_to_chat_history(user_query: str, bot_response: str, agent: str, metadata: Dict = None):
    st.session_state.chat_history.append({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "user": user_query,
        "bot": bot_response,
        "agent": agent,
        "metadata": metadata or {}
    })
    if len(st.session_state.chat_history) > 10:
        st.session_state.chat_history = st.session_state.chat_history[-10:]

def display_chat_message(message: Dict):
    with st.container():
        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(f"**{message['timestamp']}**")
            agent_color = {
                "youtubebot": "🟥",
                "docchatbot": "🟩",
                "fetchbot": "🟦",
                "pythonbot": "🟨"
            }.get(message['agent'], "⚪")
            st.markdown(f"{agent_color} {message['agent']}")
        with col2:
            st.markdown(f"**You:** {message['user']}")
            st.markdown(f"**Bot:** {message['bot']}")
        st.markdown("---")

# Fetch agents and health
if not st.session_state.available_agents:
    st.session_state.available_agents = fetch_available_agents()

if "error" in st.session_state.health_data:
    st.session_state.health_data = check_health()

# Sidebar: Health
st.sidebar.markdown("### 🔧 System Health")
health_data = st.session_state.health_data
if "error" in health_data:
    st.sidebar.markdown(f"**Router**: 🔴 {health_data['error']}")
else:
    st.sidebar.markdown(f"**Router**: 🟢 Healthy")
    for agent, status in health_data.get("agents", {}).items():
        st.sidebar.markdown(f"**{agent}**: {'🟢 Healthy' if status == 'healthy' else '🔴 Unhealthy'}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔄 Session Management")
st.sidebar.markdown(f"**Session ID**: `{st.session_state.session_id[:8]}...`")

if st.sidebar.button("🔄 New Session"):
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.chat_history = []
    st.session_state.available_agents = []
    st.session_state.health_data = {"error": "Not checked"}
    st.session_state.document_uploaded = False
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 Available Agents")
for agent in st.session_state.available_agents:
    st.sidebar.markdown(f"- {agent}")

# Main UI
st.title("🤖 MCP Orchestrator - Chat Interface")
st.markdown("Ask me anything, and I'll route your query to the appropriate agent!")

# Document Upload Form
with st.form(key="upload_form", clear_on_submit=True):
    uploaded_file = st.file_uploader("Upload a document (optional):", type=["pdf", "txt", "docx"])
    submit_upload = st.form_submit_button("📤 Upload Document", use_container_width=True)

if submit_upload and uploaded_file:
    with st.spinner("Uploading document..."):
        upload_result = upload_document(uploaded_file, st.session_state.session_id)
        if "error" in upload_result:
            st.error(f"❌ File upload failed: {upload_result['error']}")
            add_to_chat_history("Document upload", upload_result['error'], "system")
        else:
            st.success("✅ Document uploaded successfully. You can now ask questions about it, e.g., 'What is the summary?', 'What is the sentiment?', or specific questions.")
            st.session_state.document_uploaded = True
            add_to_chat_history("Document upload", "Document uploaded successfully.", "system")

# Chat Input Form
with st.form(key="chat_form", clear_on_submit=True):
    user_query = st.text_area(
        "Your query:",
        placeholder="e.g., 'Summarize this YouTube video: [URL]', 'Fetch and summarize [URL]', 'Execute this Python code:\nnum1 = 1.5\nnum2 = 6.3\nsum = num1 + num2\nprint(\"The sum is\", sum)', or 'What is the summary?' after uploading a document",
        height=100
    )
    submit_query = st.form_submit_button("🚀 Send Query", use_container_width=True)

if submit_query and user_query:
    with st.spinner("Processing your query..."):
        request_data = {
            "session_id": st.session_state.session_id,
            "query": user_query
        }
        # Prefer MCP-style router endpoint; fall back to legacy if needed
        result = make_request("/fastmcp", request_data)
        if "error" in result:
            # fallback to legacy
            result = make_request("/query", request_data)
        if "error" in result:
            st.error(f"❌ {result['error']}")
            add_to_chat_history(user_query, result['error'], "system")
        else:
            response = result.get("reply", result.get("response", "No response"))
            agent = result.get("intent", result.get("agent", "unknown"))
            st.success(f"💬 {response}")
            add_to_chat_history(user_query, response, agent)

# Chat History
if st.session_state.chat_history:
    st.markdown("---")
    st.markdown("### 💬 Recent Chat History")
    recent_messages = st.session_state.chat_history[-5:]
    for message in reversed(recent_messages):
        display_chat_message(message)

# Footer Tips
st.markdown("---")
st.markdown("### 💡 Tips")
st.markdown("- You can ask about YouTube videos, documents, web content, or Python code.")
st.markdown("- The system will automatically route your query to the appropriate agent.")
st.markdown("- For YouTube videos, include the URL, e.g., 'Summarize this video: [URL]' or just the URL.")
st.markdown("- For web content, specify the URL, e.g., 'Fetch and summarize [URL]' or just the URL.")
st.markdown("- For documents, upload a file first, then ask questions like 'What is the summary?' or 'What is the sentiment?'.")
st.markdown("- For Python code, use the text area with proper indentation, e.g., 'Execute this Python code: [code]'.")
st.markdown("- Note: Interactive code with input() is not supported. Please hardcode your input values.")