# backend/fetch_mcp.py - Fetch MCP server
import logging
import requests
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from mcp.server import Server
from mcp.server.fastmcp import FastMCP
import uvicorn
import os

from backend.agent_core import extract_url_from_query

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("fetch-mcp")
app = FastMCP(server)

def fetch_web_content(url: str) -> tuple[str, bool]:
    """Fetch content from a URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        text = text[:2000]  # Limit text length
        return text, True
    except Exception as e:
        logger.error(f"Error fetching {url}: {str(e)}")
        return f"Error: {str(e)}", False

def summarize_text(text: str) -> str:
    """Summarize text by taking first 200 words"""
    words = text.split()[:200]
    return " ".join(words)

@server.tool("fetch_url")
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

@server.tool("fetch_andSummarize")
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

@server.tool("query")
async def query_tool(
    session_id: str,
    query: str,
    url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle fetch queries with optional URL extraction.
    """
    try:
        logger.info(f"Query: {query}, URL: {url}")
        
        # Extract URL from query if not provided
        if not url:
            url = extract_url_from_query(query)
        
        if not url:
            return {
                "reply": "Please provide a URL to fetch.",
                "intent": "fetchbot",
                "success": False,
                "session_id": session_id
            }
        
        # Check if summarization is requested
        if any(word in query.lower() for word in ["summarize", "summary", "summarise"]):
            return await fetch_andSummarize_tool(session_id, url)
        else:
            return await fetch_url_tool(session_id, url)
            
    except Exception as e:
        logger.error(f"Error in query_tool: {str(e)}")
        return {
            "reply": f"Error processing fetch query: {str(e)}",
            "intent": "fetchbot",
            "success": False,
            "session_id": session_id
        }

@server.tool("health")
async def health_tool() -> Dict[str, Any]:
    """
    Check the health of the Fetch MCP server.
    """
    try:
        return {
            "reply": "Fetch MCP server is healthy",
            "intent": "health_check",
            "success": True,
            "status": "healthy"
        }
    except Exception as e:
        logger.error(f"Error in health_tool: {str(e)}")
        return {
            "reply": f"Fetch MCP server health check failed: {str(e)}",
            "intent": "health_check",
            "success": False,
            "status": "unhealthy"
        }

@server.tool("extract_url")
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

if __name__ == "__main__":
    logger.info("Starting Fetch MCP Server (FastMCP)...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8004")))