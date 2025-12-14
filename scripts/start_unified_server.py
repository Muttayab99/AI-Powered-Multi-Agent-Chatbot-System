#!/usr/bin/env python3
"""
Startup script for the unified MCP server.
This script launches a single server that combines all functionality.
"""

import os
import sys
import subprocess
import signal
import time

def start_unified_server():
    """Start the unified MCP server"""
    print("Starting Unified MCP Server...")
    
    # Set environment variables
    env = os.environ.copy()
    env['PORT'] = '8000'
    
    try:
        # Start the unified server
        unified_script = os.path.join(os.path.dirname(__file__), '..', 'servers', 'unified_mcp.py')
        process = subprocess.Popen(
            [sys.executable, unified_script],
            env=env,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        print(f"Unified MCP server started with PID: {process.pid}")
        print("Server is running at: http://localhost:8000")
        print("MCP configuration: backend/mcp_config_unified.json")
        print("\nAvailable tools:")
        print("- YouTube: process_video, chat_with_video, query_video, list_videos")
        print("- Documents: upload_document, ask_question, summarize, sentiment")
        print("- Python: execute_python, validate_code")
        print("- Web: fetch_url, fetchandSummarize, extract_url")
        print("- Session: route, session_info, list_sessions, clear_session")
        print("- Health: health, list_all_tools")
        
        return process
        
    except Exception as e:
        print(f"Error starting unified server: {e}")
        return None

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\nShutting down unified MCP server...")
    sys.exit(0)

def main():
    """Main function"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("UNIFIED MCP SERVER STARTUP")
    print("=" * 60)
    
    # Start the server
    process = start_unified_server()
    
    if process:
        try:
            # Wait for the process to complete
            process.wait()
        except KeyboardInterrupt:
            print("\nReceived interrupt signal, shutting down...")
            process.terminate()
            process.wait()
            print("Unified MCP server stopped.")
    else:
        print("Failed to start unified MCP server.")
        sys.exit(1)

if __name__ == "__main__":
    main()
