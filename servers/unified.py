# backend/unified_mcp.py - Unified MCP server combining all services
import os
import json
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any, List
import logging
import yt_dlp
import torch
import re
import io
import sys
from pathlib import Path
import PyPDF2
from docx import Document as DocxDocument
from bs4 import BeautifulSoup

from fastmcp import FastMCP
import uvicorn

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_community.llms import HuggingFacePipeline

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create unified MCP server
app = FastMCP("unified-mcp")

# Global storage
vector_db_store = {}  # YouTube videos
vectorstores = {}     # Documents
full_texts = {}       # Document full texts
session_states = {}   # Session management

# Import agent_core functions
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.agent_core import (
    get_session_state, update_session_state, detect_intent,
    clear_session, get_all_sessions, is_safe_python_expression,
    extract_url_from_query
)

# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================

# ============================================================================
# ROUTING AND SESSION MANAGEMENT TOOLS
# ============================================================================

@app.tool("route")
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

@app.tool("session_info")
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

@app.tool("list_sessions")
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

@app.tool("clear_session")
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

# ============================================================================
# YOUTUBE TOOLS
# ============================================================================

@app.tool("process_video")
async def process_video_tool(video_url: str) -> Dict[str, Any]:
    """
    Process a YouTube video to extract transcript and prepare for Q&A.
    """
    try:
        video_id = process_video(video_url)
        return {
            "reply": f"Video processed successfully. Video ID: {video_id}",
            "intent": "youtubebot",
            "success": True,
            "video_id": video_id
        }
    except Exception as e:
        return {
            "reply": f"Error processing video: {str(e)}",
            "intent": "youtubebot",
            "success": False,
            "error": str(e)
        }

@app.tool("chat_with_video")
async def chat_with_video_tool(video_url: str, query: str) -> Dict[str, Any]:
    """
    Chat with a YouTube video by asking questions about its content.
    """
    try:
        if not query:
            return {
                "reply": "Missing query parameter.",
                "intent": "youtubebot",
                "success": False
            }

        if not video_url:
            return {
                "reply": "Please provide a YouTube video URL to analyze.",
                "intent": "youtubebot",
                "success": False
            }

        result = run_qa_with_flan_t5(video_url, query)
        
        if "error" in result:
            return {
                "reply": result["error"],
                "intent": "youtubebot",
                "success": False
            }

        return {
            "reply": result["response"],
            "intent": "youtubebot",
            "success": True
        }
        
    except Exception as e:
        error_msg = f"YouTube Bot Error: {str(e)}"
        logging.error(error_msg)
        return {
            "reply": error_msg,
            "intent": "youtubebot",
            "success": False
        }

@app.tool("query_video")
async def query_video_tool(
    session_id: str,
    query: str,
    video_url: str
) -> Dict[str, Any]:
    """
    Query a YouTube video with a question. This is the main tool for video Q&A.
    """
    try:
        if not query:
            return {
                "reply": "Missing query parameter.",
                "intent": "youtubebot",
                "success": False,
                "session_id": session_id
            }

        if not video_url:
            return {
                "reply": "Please provide a YouTube video URL to analyze.",
                "intent": "youtubebot",
                "success": False,
                "session_id": session_id
            }

        result = run_qa_with_flan_t5(video_url, query)
        
        if "error" in result:
            return {
                "reply": result["error"],
                "intent": "youtubebot",
                "success": False,
                "session_id": session_id
            }

        return {
            "reply": result["response"],
            "intent": "youtubebot",
            "success": True,
            "session_id": session_id
        }
        
    except Exception as e:
        error_msg = f"YouTube Bot Error: {str(e)}"
        logging.error(error_msg)
        return {
            "reply": error_msg,
            "intent": "youtubebot",
            "success": False,
            "session_id": session_id
        }

@app.tool("list_videos")
async def list_videos_tool() -> Dict[str, Any]:
    """
    List all processed videos.
    """
    try:
        video_ids = list(vector_db_store.keys())
        return {
            "reply": f"Found {len(video_ids)} processed videos",
            "intent": "video_management",
            "success": True,
            "videos": video_ids
        }
    except Exception as e:
        logger.error(f"Error in list_videos_tool: {str(e)}")
        return {
            "reply": f"Error listing videos: {str(e)}",
            "intent": "video_management",
            "success": False
        }

# ============================================================================
# DOCUMENT TOOLS
# ============================================================================

@app.tool("upload_document")
async def upload_document_tool(
    session_id: str,
    file_path: str
) -> Dict[str, Any]:
    """
    Upload and process a document for Q&A.
    """
    try:
        result = process_document(file_path, session_id)
        
        if result["success"]:
            return {
                "reply": f"Document uploaded and processed successfully. {result['text_length']} characters, {result['chunks']} chunks created.",
                "intent": "docchatbot",
                "success": True,
                "session_id": session_id,
                "file_name": result["file_name"]
            }
        else:
            return {
                "reply": f"Error processing document: {result['error']}",
                "intent": "docchatbot",
                "success": False,
                "session_id": session_id
            }
            
    except Exception as e:
        logger.error(f"Error in upload_document_tool: {str(e)}")
        return {
            "reply": f"Error uploading document: {str(e)}",
            "intent": "docchatbot",
            "success": False,
            "session_id": session_id
        }

@app.tool("ask_question")
async def ask_question_tool(
    session_id: str,
    question: str
) -> Dict[str, Any]:
    """
    Ask a question about the uploaded document.
    """
    try:
        vectorstore = vectorstores.get(session_id)
        if not vectorstore:
            return {
                "reply": "No document uploaded for this session. Please upload a document first.",
                "intent": "docchatbot",
                "success": False,
                "session_id": session_id
            }
        
        response = ask_question(vectorstore, question)
        return {
            "reply": response,
            "intent": "docchatbot",
            "success": True,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Error in ask_question_tool: {str(e)}")
        return {
            "reply": f"Error processing question: {str(e)}",
            "intent": "docchatbot",
            "success": False,
            "session_id": session_id
        }

@app.tool("summarize")
async def summarize_tool(session_id: str) -> Dict[str, Any]:
    """
    Get a summary of the uploaded document.
    """
    try:
        full_text = full_texts.get(session_id)
        if not full_text:
            return {
                "reply": "No document uploaded for this session. Please upload a document first.",
                "intent": "docchatbot",
                "success": False,
                "session_id": session_id
            }
        
        summary = summarize(full_text)
        return {
            "reply": summary,
            "intent": "docchatbot",
            "success": True,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Error in summarize_tool: {str(e)}")
        return {
            "reply": f"Error creating summary: {str(e)}",
            "intent": "docchatbot",
            "success": False,
            "session_id": session_id
        }

@app.tool("sentiment")
async def sentiment_tool(session_id: str) -> Dict[str, Any]:
    """
    Get sentiment analysis of the uploaded document.
    """
    try:
        full_text = full_texts.get(session_id)
        if not full_text:
            return {
                "reply": "No document uploaded for this session. Please upload a document first.",
                "intent": "docchatbot",
                "success": False,
                "session_id": session_id
            }
        
        sentiment = get_sentiment(full_text)
        return {
            "reply": f"Document sentiment: {sentiment}",
            "intent": "docchatbot",
            "success": True,
            "session_id": session_id,
            "sentiment": sentiment
        }
        
    except Exception as e:
        logger.error(f"Error in sentiment_tool: {str(e)}")
        return {
            "reply": f"Error analyzing sentiment: {str(e)}",
            "intent": "docchatbot",
            "success": False,
            "session_id": session_id
        }

@app.tool("list_document_sessions")
async def list_document_sessions_tool() -> Dict[str, Any]:
    """
    List all active document sessions.
    """
    try:
        sessions = list(vectorstores.keys())
        return {
            "reply": f"Found {len(sessions)} active document sessions",
            "intent": "docchatbot",
            "success": True,
            "sessions": sessions
        }
    except Exception as e:
        logger.error(f"Error in list_document_sessions_tool: {str(e)}")
        return {
            "reply": f"Error listing sessions: {str(e)}",
            "intent": "docchatbot",
            "success": False
        }

@app.tool("clear_document_session")
async def clear_document_session_tool(session_id: str) -> Dict[str, Any]:
    """
    Clear a specific document session.
    """
    try:
        if session_id in vectorstores:
            del vectorstores[session_id]
        if session_id in full_texts:
            del full_texts[session_id]
        
        return {
            "reply": f"Document session {session_id} cleared successfully",
            "intent": "docchatbot",
            "success": True,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error in clear_document_session_tool: {str(e)}")
        return {
            "reply": f"Error clearing document session: {str(e)}",
            "intent": "docchatbot",
            "success": False,
            "session_id": session_id
        }

# ============================================================================
# PYTHON EXECUTION TOOLS
# ============================================================================

@app.tool("execute_python")
async def execute_python_tool(
    session_id: str,
    code: str
) -> Dict[str, Any]:
    """
    Execute Python code safely.
    """
    try:
        if not code.strip():
            return {
                "reply": "Provide a Python expression.",
                "intent": "pythonbot",
                "success": False,
                "session_id": session_id
            }
        
        result = execute_python(code)
        return {
            "reply": result,
            "intent": "pythonbot",
            "success": True,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error in execute_python_tool: {str(e)}")
        return {
            "reply": f"Error executing Python code: {str(e)}",
            "intent": "pythonbot",
            "success": False,
            "session_id": session_id
        }

@app.tool("validate_code")
async def validate_code_tool(
    session_id: str,
    code: str
) -> Dict[str, Any]:
    """
    Validate Python code without executing it.
    """
    try:
        if not code.strip():
            return {
                "reply": "Provide Python code to validate.",
                "intent": "pythonbot",
                "success": False,
                "session_id": session_id
            }
        
        is_safe = is_safe_python_expression(code)
        if is_safe:
            return {
                "reply": "Code is safe to execute.",
                "intent": "pythonbot",
                "success": True,
                "session_id": session_id,
                "validation": "safe"
            }
        else:
            return {
                "reply": "Code contains potentially unsafe operations.",
                "intent": "pythonbot",
                "success": False,
                "session_id": session_id,
                "validation": "unsafe"
            }
    except Exception as e:
        logger.error(f"Error in validate_code_tool: {str(e)}")
        return {
            "reply": f"Error validating code: {str(e)}",
            "intent": "pythonbot",
            "success": False,
            "session_id": session_id
        }

# ============================================================================
# WEB FETCHING TOOLS
# ============================================================================

@app.tool("fetch_url")
async def fetch_url_tool(
    session_id: str,
    url: str
) -> Dict[str, Any]:
    """
    Fetch content from a specific URL.
    """
    try:
        if not url:
            return {
                "reply": "Please provide a URL to fetch.",
                "intent": "fetchbot",
                "success": False,
                "session_id": session_id
            }
        
        content, success = fetch_web_content(url)
        if not success:
            return {
                "reply": content,
                "intent": "fetchbot",
                "success": False,
                "session_id": session_id
            }
        
        return {
            "reply": content,
            "intent": "fetchbot",
            "success": True,
            "session_id": session_id,
            "url": url
        }
    except Exception as e:
        logger.error(f"Error in fetch_url_tool: {str(e)}")
        return {
            "reply": f"Error fetching URL: {str(e)}",
            "intent": "fetchbot",
            "success": False,
            "session_id": session_id
        }

@app.tool("fetch_andSummarize")
async def fetch_andSummarize_tool(
    session_id: str,
    url: str
) -> Dict[str, Any]:
    """
    Fetch content from a URL and provide a summary.
    """
    try:
        if not url:
            return {
                "reply": "Please provide a URL to fetch and summarize.",
                "intent": "fetchbot",
                "success": False,
                "session_id": session_id
            }
        
        content, success = fetch_web_content(url)
        if not success:
            return {
                "reply": content,
                "intent": "fetchbot",
                "success": False,
                "session_id": session_id
            }
        
        summary = summarize_text(content)
        return {
            "reply": summary,
            "intent": "fetchbot",
            "success": True,
            "session_id": session_id,
            "url": url,
            "summary": True
        }
    except Exception as e:
        logger.error(f"Error in fetchAndSummarize_tool: {str(e)}")
        return {
            "reply": f"Error fetching and summarizing URL: {str(e)}",
            "intent": "fetchbot",
            "success": False,
            "session_id": session_id
        }

@app.tool("extract_url")
async def extract_url_tool(
    session_id: str,
    query: str
) -> Dict[str, Any]:
    """
    Extract URL from a query text.
    """
    try:
        url = extract_url_from_query(query)
        if url:
            return {
                "reply": f"Extracted URL: {url}",
                "intent": "fetchbot",
                "success": True,
                "session_id": session_id,
                "extracted_url": url
            }
        else:
            return {
                "reply": "No URL found in the query.",
                "intent": "fetchbot",
                "success": False,
                "session_id": session_id
            }
    except Exception as e:
        logger.error(f"Error in extract_url_tool: {str(e)}")
        return {
            "reply": f"Error extracting URL: {str(e)}",
            "intent": "fetchbot",
            "success": False,
            "session_id": session_id
        }

# ============================================================================
# HEALTH AND UTILITY TOOLS
# ============================================================================

@app.tool("health")
async def health_tool() -> Dict[str, Any]:
    """
    Check the health of the unified MCP server.
    """
    try:
        session_count = len(get_all_sessions())
        video_count = len(vector_db_store)
        doc_session_count = len(vectorstores)
        
        return {
            "reply": f"Unified MCP server is healthy with {session_count} active sessions, {video_count} processed videos, and {doc_session_count} document sessions",
            "intent": "health_check",
            "success": True,
            "status": "healthy",
            "session_count": session_count,
            "video_count": video_count,
            "document_sessions": doc_session_count
        }
    except Exception as e:
        logger.error(f"Error in health_tool: {str(e)}")
        return {
            "reply": f"Unified MCP server health check failed: {str(e)}",
            "intent": "health_check",
            "success": False,
            "status": "unhealthy"
        }

@app.tool("list_all_tools")
async def list_all_tools_tool() -> Dict[str, Any]:
    """
    List all available tools in the unified MCP server.
    """
    try:
        tools = [
            "route", "session_info", "list_sessions", "clear_session",
            "process_video", "chat_with_video", "query_video", "list_videos",
            "upload_document", "ask_question", "summarize", "sentiment", 
            "list_document_sessions", "clear_document_session",
            "execute_python", "validate_code",
            "fetch_url", "fetchandSummarize", "extract_url",
            "health", "list_all_tools"
        ]
        
        return {
            "reply": f"Available tools: {', '.join(tools)}",
            "intent": "tool_listing",
            "success": True,
            "tools": tools,
            "tool_count": len(tools)
        }
    except Exception as e:
        logger.error(f"Error in list_all_tools_tool: {str(e)}")
        return {
            "reply": f"Error listing tools: {str(e)}",
            "intent": "tool_listing",
            "success": False
        }

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting Unified MCP Server (FastMCP)...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
