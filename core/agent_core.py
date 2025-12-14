# backend/agent_core.py - Shared core logic for MCP servers
import os
import re
import uuid
import logging
import socket
import asyncio
from typing import Optional, List, Dict, Any
from groq import Groq

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Agent endpoints (these will be MCP servers, not HTTP)
AGENT_ENDPOINTS = {
    "youtubebot": "youtube-mcp",
    "docchatbot": "document-mcp", 
    "pythonbot": "python-mcp",
    "fetchbot": "fetch-mcp"
}

# Session state management
session_states: Dict[str, Dict[str, Any]] = {}

def get_session_state(session_id: str) -> Dict[str, Any]:
    if session_id not in session_states:
        session_states[session_id] = {
            "session_id": session_id,
            "history": [],
            "context": {}
        }
    return session_states[session_id]

def update_session_state(session_id: str, new_state: Dict[str, Any]) -> None:
    session_states[session_id] = new_state

def clear_session(session_id: str) -> bool:
    if session_id in session_states:
        del session_states[session_id]
        return True
    return False

def get_all_sessions() -> List[str]:
    return list(session_states.keys())

# Intent detection using GROQ API
def detect_intent(query: str, context: Dict[str, Any] = None) -> str:
    try:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY not set, using default intent detection")
            # Simple keyword-based fallback
            query_lower = query.lower()
            if any(word in query_lower for word in ["youtube", "video", "summarize video"]):
                return "youtubebot"
            elif any(word in query_lower for word in ["document", "pdf", "upload"]):
                return "docchatbot"
            elif any(word in query_lower for word in ["fetch", "url", "website", "summarize"]):
                return "fetchbot"
            elif any(word in query_lower for word in ["python", "code", "execute", "print"]):
                return "pythonbot"
            else:
                return "docchatbot"  # Default
        
        client = Groq(api_key=api_key)
        system_prompt = """Classify user queries into: youtubebot, docchatbot, fetchbot, pythonbot. Respond with only the category name.
        Examples:
        - "Summarize this video: [URL]" -> youtubebot
        - "Summarize a document" -> docchatbot
        - "Fetch and summarize [URL]" -> fetchbot
        - "Execute this code: [code]" -> pythonbot"""
        
        context_info = ""
        if context:
            if context.get("video_url"):
                context_info += f"\nContext: Video URL: {context['video_url']}"
            if context.get("document_id"):
                context_info += f"\nContext: Document: {context['document_id']}"
        
        user_prompt = f"Query: {query}{context_info}"
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
            max_completion_tokens=20
        )
        label = completion.choices[0].message.content.strip().lower()
        return label if label in AGENT_ENDPOINTS else "docchatbot"
    except Exception as e:
        logger.error(f"Intent detection error: {str(e)}")
        return "docchatbot"

# Utility functions
def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/v\/([^&\n?#]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return url

def extract_url_from_query(query: str) -> Optional[str]:
    """Extract URL from query text"""
    url_patterns = [
        r'https?://[^\s]+',
        r'www\.[^\s]+',
        r'[^\s]+\.com[^\s]*',
        r'[^\s]+\.org[^\s]*',
        r'[^\s]+\.net[^\s]*',
        r'[^\s]+\.edu[^\s]*',
        r'[^\s]+\.gov[^\s]*',
    ]
    
    for pattern in url_patterns:
        match = re.search(pattern, query)
        if match:
            url = match.group(0)
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            return url
    
    return None

def is_safe_python_expression(code: str) -> bool:
    """Check if Python code is safe to execute"""
    code = code.strip()
    if code.startswith("execute this python code"):
        code = code.replace("execute this python code", "").strip()
    if code.startswith("execute this python code:"):
        code = code.replace("execute this python code:", "").strip()
    if code.startswith("[") and code.endswith("]"):
        code = code[1:-1].strip()
    
    dangerous_keywords = [
        'import', 'from', 'exec', 'eval', 'open', 'file', 'os.', 'sys.',
        'subprocess', 'globals', 'locals', '__', 'del', 'raise', 'input'
    ]
    
    for keyword in dangerous_keywords:
        if keyword in code:
            return False
    
    return True
