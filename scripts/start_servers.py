#!/usr/bin/env python3
"""
Startup script for all MCP servers (SSE mode).
This script launches each MCP server with uvicorn on separate ports for local dev or cloud deployment.
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path

# MCP server configurations
MCP_SERVERS = [
    {
        "name": "agent-router",
        "script": "servers/router_mcp.py",
        "description": "Main router for coordinating between agents",
        "port": 8000
    },
    {
        "name": "youtube-mcp", 
        "script": "servers/youtube_mcp.py",
        "description": "YouTube video processing and Q&A",
        "port": 8001
    },
    {
        "name": "document-mcp",
        "script": "servers/document_mcp.py", 
        "description": "Document processing and Q&A",
        "port": 8002
    },
    {
        "name": "python-mcp",
        "script": "servers/python_mcp.py",
        "description": "Python code execution",
        "port": 8003
    },
    {
        "name": "fetch-mcp",
        "script": "servers/fetch_mcp.py",
        "description": "Web content fetching and summarization",
        "port": 8004
    }
]

# Store process references
processes = []

def start_server(server_config):
    """Start a single MCP server"""
    try:
        script_path = Path(__file__).parent.parent / server_config["script"]
        
        print(f"Starting {server_config['name']}...")
        print(f"  Description: {server_config['description']}")
        print(f"  Script: {script_path}")
        
        # Start the process
        env = os.environ.copy()
        if "port" in server_config:
            env["PORT"] = str(server_config["port"])

        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=env
        )
        
        processes.append({
            "name": server_config["name"],
            "process": process,
            "config": server_config
        })
        
        print(f"  OK {server_config['name']} started (PID: {process.pid})")
        return True
        
    except Exception as e:
        print(f"  ERROR Failed to start {server_config['name']}: {e}")
        return False

def start_all_servers():
    """Start all MCP servers"""
    print("Starting MCP Servers...")
    print("=" * 50)
    
    success_count = 0
    for server_config in MCP_SERVERS:
        if start_server(server_config):
            success_count += 1
        print()
    
    print(f"Started {success_count}/{len(MCP_SERVERS)} MCP servers")
    return success_count == len(MCP_SERVERS)

def stop_all_servers():
    """Stop all running MCP servers"""
    print("\nStopping MCP Servers...")
    
    for proc_info in processes:
        try:
            process = proc_info["process"]
            if process.poll() is None:  # Process is still running
                print(f"Stopping {proc_info['name']} (PID: {process.pid})...")
                process.terminate()
                process.wait(timeout=5)
                print(f"  OK {proc_info['name']} stopped")
            else:
                print(f"  OK {proc_info['name']} already stopped")
        except Exception as e:
            print(f"  ERROR stopping {proc_info['name']}: {e}")
    
    processes.clear()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\nReceived signal {signum}, shutting down...")
    stop_all_servers()
    sys.exit(0)

def monitor_servers():
    """Monitor running servers and show status"""
    print("\nServer Status:")
    print("-" * 30)
    
    for proc_info in processes:
        process = proc_info["process"]
        status = "Running" if process.poll() is None else "Stopped"
        print(f"{proc_info['name']:15} | {status:10} | PID: {process.pid}")

def main():
    """Main function"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Check if GROQ_API_KEY is set
        if not os.getenv("GROQ_API_KEY"):
            print("⚠️  Warning: GROQ_API_KEY environment variable not set")
            print("   Some features may not work properly")
            print()
        
        # Start all servers
        if not start_all_servers():
            print("Some servers failed to start. Exiting.")
            return 1
        
        print("\nAll MCP servers started successfully!")
        print("\nAvailable MCP servers:")
        for server_config in MCP_SERVERS:
            print(f"  - {server_config['name']}: {server_config['description']}")
        
        print("\nTo use these servers:")
        print("   1. Configure your MCP client with backend/mcp_config.json (SSE URLs)")
        print("   2. Or manually add each server to your MCP client as type=\"sse\"")
        print("   3. Endpoints are exposed at /sse over HTTP for MCP protocol")
        
        print("\nServers are running. Press Ctrl+C to stop all servers.")
        
        # Monitor servers
        while True:
            time.sleep(10)
            monitor_servers()
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        stop_all_servers()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
