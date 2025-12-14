# backend/router_mcp.py - Main router MCP server
import asyncio
import logging
import os
from typing import Optional, List, Dict, Any
from mcp.server import Server
from mcp.server.fastmcp import FastMCP
import uvicorn

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.agent_core import (
    get_session_state, update_session_state, detect_intent,
    clear_session, get_all_sessions
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("agent-router")
app = FastMCP(server)

@server.tool("route")
async def route_tool(
    session_id: str,
    query: str,
    video_url: Optional[str] = None,
    document_id: Optional[str] = None,
    url: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Route a query to the appropriate agent based on intent detection.
    This tool automatically determines which agent should handle the query.
    """
    try:
        state = get_session_state(session_id)
        
        # Update session state with new context
        if video_url: 
            state["video_url"] = video_url
        if document_id: 
            state["document_id"] = document_id
        if url: 
            state["url"] = url
        if history: 
            state["history"] = history

        # Detect intent
        agent_name = detect_intent(query, state)
        logger.info(f"Routing query to {agent_name}: {query}")
        
        # For now, return the routing decision
        # In a full MCP setup, this would call the appropriate agent MCP server
        return {
            "reply": f"Query routed to {agent_name}. Use the specific agent tool for execution.",
            "intent": agent_name,
            "success": True,
            "session_id": session_id,
            "routing_info": {
                "detected_agent": agent_name,
                "query": query,
                "context": state
            }
        }
        
    except Exception as e:
        logger.error(f"Error in route_tool: {str(e)}")
        return {
            "reply": f"Error processing request: {str(e)}",
            "intent": "error",
            "success": False,
            "session_id": session_id
        }

@server.tool("youtubebot")
async def youtube_tool(
    session_id: str, 
    query: str, 
    video_url: str
) -> Dict[str, Any]:
    """
    Handle YouTube video queries directly.
    """
    try:
        state = get_session_state(session_id)
        state["video_url"] = video_url
        
        # This would call the YouTube MCP server in a full setup
        return {
            "reply": f"YouTube query processed: {query} for video {video_url}",
            "intent": "youtubebot",
            "success": True,
            "session_id": session_id,
            "video_url": video_url
        }
    except Exception as e:
        logger.error(f"Error in youtube_tool: {str(e)}")
        return {
            "reply": f"Error processing YouTube query: {str(e)}",
            "intent": "youtubebot",
            "success": False,
            "session_id": session_id
        }

@server.tool("docchatbot")
async def document_tool(
    session_id: str, 
    query: str,
    document_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle document queries directly.
    """
    try:
        state = get_session_state(session_id)
        if document_id:
            state["document_id"] = document_id
        
        # This would call the Document MCP server in a full setup
        return {
            "reply": f"Document query processed: {query}",
            "intent": "docchatbot",
            "success": True,
            "session_id": session_id,
            "document_id": document_id
        }
    except Exception as e:
        logger.error(f"Error in document_tool: {str(e)}")
        return {
            "reply": f"Error processing document query: {str(e)}",
            "intent": "docchatbot",
            "success": False,
            "session_id": session_id
        }

@server.tool("fetchbot")
async def fetch_tool(
    session_id: str, 
    query: str, 
    url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle web fetching queries directly.
    """
    try:
        state = get_session_state(session_id)
        if url:
            state["url"] = url
        
        # This would call the Fetch MCP server in a full setup
        return {
            "reply": f"Fetch query processed: {query}",
            "intent": "fetchbot",
            "success": True,
            "session_id": session_id,
            "url": url
        }
    except Exception as e:
        logger.error(f"Error in fetch_tool: {str(e)}")
        return {
            "reply": f"Error processing fetch query: {str(e)}",
            "intent": "fetchbot",
            "success": False,
            "session_id": session_id
        }

@server.tool("pythonbot")
async def python_tool(
    session_id: str, 
    query: str
) -> Dict[str, Any]:
    """
    Handle Python code execution queries directly.
    """
    try:
        state = get_session_state(session_id)
        
        # This would call the Python MCP server in a full setup
        return {
            "reply": f"Python query processed: {query}",
            "intent": "pythonbot",
            "success": True,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error in python_tool: {str(e)}")
        return {
            "reply": f"Error processing Python query: {str(e)}",
            "intent": "pythonbot",
            "success": False,
            "session_id": session_id
        }

@server.tool("session_info")
async def session_info_tool(session_id: str) -> Dict[str, Any]:
    """
    Get information about a specific session.
    """
    try:
        state = get_session_state(session_id)
        return {
            "reply": f"Session {session_id} info retrieved",
            "intent": "session_management",
            "success": True,
            "session_id": session_id,
            "session_data": state
        }
    except Exception as e:
        logger.error(f"Error in session_info_tool: {str(e)}")
        return {
            "reply": f"Error getting session info: {str(e)}",
            "intent": "session_management",
            "success": False,
            "session_id": session_id
        }

@server.tool("list_sessions")
async def list_sessions_tool() -> Dict[str, Any]:
    """
    List all active sessions.
    """
    try:
        sessions = get_all_sessions()
        return {
            "reply": f"Found {len(sessions)} active sessions",
            "intent": "session_management",
            "success": True,
            "sessions": sessions
        }
    except Exception as e:
        logger.error(f"Error in list_sessions_tool: {str(e)}")
        return {
            "reply": f"Error listing sessions: {str(e)}",
            "intent": "session_management",
            "success": False
        }

@server.tool("clear_session")
async def clear_session_tool(session_id: str) -> Dict[str, Any]:
    """
    Clear a specific session.
    """
    try:
        success = clear_session(session_id)
        if success:
            return {
                "reply": f"Session {session_id} cleared successfully",
                "intent": "session_management",
                "success": True,
                "session_id": session_id
            }
        else:
            return {
                "reply": f"Session {session_id} not found",
                "intent": "session_management",
                "success": False,
                "session_id": session_id
            }
    except Exception as e:
        logger.error(f"Error in clear_session_tool: {str(e)}")
        return {
            "reply": f"Error clearing session: {str(e)}",
            "intent": "session_management",
            "success": False,
            "session_id": session_id
        }

@server.tool("health")
async def health_tool() -> Dict[str, Any]:
    """
    Check the health of the router.
    """
    try:
        session_count = len(get_all_sessions())
        return {
            "reply": f"Router is healthy with {session_count} active sessions",
            "intent": "health_check",
            "success": True,
            "status": "healthy",
            "session_count": session_count
        }
    except Exception as e:
        logger.error(f"Error in health_tool: {str(e)}")
        return {
            "reply": f"Router health check failed: {str(e)}",
            "intent": "health_check",
            "success": False,
            "status": "unhealthy"
        }

if __name__ == "__main__":
    logger.info("Starting Agent Router MCP Server (FastMCP)...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
