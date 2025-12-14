# MCP Servers

This directory contains all MCP (Model Context Protocol) server implementations.

## Server Files

- **router_mcp.py** - Main router server that coordinates between all agents
- **youtube_mcp.py** - YouTube video processing and Q&A server
- **document_mcp.py** - Document upload and Q&A server
- **python_mcp.py** - Python code execution server
- **fetch_mcp.py** - Web content fetching and summarization server
- **unified_mcp.py** - Single unified server combining all functionalities

## Running Servers

### Individual Server
```powershell
cd backend/servers
python router_mcp.py
```

### All Servers
```powershell
cd backend/scripts
python start_mcp_servers.py
```

## Server Ports

- Router: 8000
- YouTube: 8001
- Document: 8002
- Python: 8003
- Fetch: 8004
- Unified: 8000 (if used instead of microservices)
