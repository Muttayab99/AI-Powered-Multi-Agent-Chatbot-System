# backend/python_mcp.py - Python MCP server
import logging
import re
import io
import sys
from typing import Dict, Any
from mcp.server import Server
from mcp.server.fastmcp import FastMCP
import uvicorn
import os

from backend.agent_core import is_safe_python_expression

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("python-mcp")
app = FastMCP(server)

def execute_python(expr: str) -> str:
    """Execute Python code safely"""
    try:
        expr = expr.strip()
        if expr.startswith("execute this python code"):
            expr = expr.replace("execute this python code", "").strip()
        if expr.startswith("execute this python code:"):
            expr = expr.replace("execute this python code:", "").strip()
        if expr.startswith("[") and expr.endswith("]"):
            expr = expr[1:-1].strip()
        
        # Check for input() explicitly
        if 'input(' in expr:
            return "Error: Interactive input (input()) is not supported. Please hardcode your input values."
        
        if not is_safe_python_expression(expr):
            return "Error: This code contains potentially unsafe operations."
        
        safe_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "sorted": sorted,
                "reversed": reversed,
                "all": all,
                "any": any,
                "bool": bool,
                "chr": chr,
                "ord": ord,
                "hex": hex,
                "oct": oct,
                "bin": bin,
                "pow": pow,
                "divmod": divmod,
                "isinstance": isinstance,
                "type": type,
                "id": id,
                "hash": hash,
                "repr": repr,
                "ascii": ascii,
                "format": format,
                "vars": vars,
                "dir": dir,
                "getattr": getattr,
                "hasattr": hasattr,
                "setattr": setattr,
                "delattr": delattr,
                "property": property,
                "staticmethod": staticmethod,
                "classmethod": classmethod,
                "super": super,
                "object": object,
                "Exception": Exception,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "IndexError": IndexError,
                "KeyError": KeyError,
                "AttributeError": AttributeError,
                "NameError": NameError,
                "ZeroDivisionError": ZeroDivisionError,
                "OverflowError": OverflowError,
                "MemoryError": MemoryError,
                "RecursionError": RecursionError,
                "SyntaxError": SyntaxError,
                "IndentationError": IndentationError,
                "TabError": TabError,
                "UnicodeError": UnicodeError,
                "UnicodeDecodeError": UnicodeDecodeError,
                "UnicodeEncodeError": UnicodeEncodeError,
                "UnicodeTranslateError": UnicodeTranslateError,
                "Warning": Warning,
                "UserWarning": UserWarning,
                "DeprecationWarning": DeprecationWarning,
                "PendingDeprecationWarning": PendingDeprecationWarning,
                "SyntaxWarning": SyntaxWarning,
                "RuntimeWarning": RuntimeWarning,
                "FutureWarning": FutureWarning,
                "ImportWarning": ImportWarning,
                "UnicodeWarning": UnicodeWarning,
                "BytesWarning": BytesWarning,
                "ResourceWarning": ResourceWarning,
                "ConnectionError": ConnectionError,
                "BlockingIOError": BlockingIOError,
                "BrokenPipeError": BrokenPipeError,
                "ChildProcessError": ChildProcessError,
                "ConnectionAbortedError": ConnectionAbortedError,
                "ConnectionRefusedError": ConnectionRefusedError,
                "ConnectionResetError": ConnectionResetError,
                "FileExistsError": FileExistsError,
                "FileNotFoundError": FileNotFoundError,
                "IsADirectoryError": IsADirectoryError,
                "NotADirectoryError": NotADirectoryError,
                "InterruptedError": InterruptedError,
                "PermissionError": PermissionError,
                "ProcessLookupError": ProcessLookupError,
                "TimeoutError": TimeoutError,
                "OSError": OSError,
                "EOFError": EOFError,
                "RuntimeError": RuntimeError,
                "NotImplementedError": NotImplementedError,
                "ArithmeticError": ArithmeticError,
                "BufferError": BufferError,
                "LookupError": LookupError,
                "AssertionError": AssertionError,
                "SystemError": SystemError,
                "ReferenceError": ReferenceError,
                "GeneratorExit": GeneratorExit,
                "StopIteration": StopIteration,
                "KeyboardInterrupt": KeyboardInterrupt,
                "SystemExit": SystemExit,
                "BaseException": BaseException,
            }
        }
        
        old_stdout = sys.stdout
        redirected_output = io.StringIO()
        sys.stdout = redirected_output
        try:
            exec(expr, safe_globals)
            result = redirected_output.getvalue()
        finally:
            sys.stdout = old_stdout
        return result.strip() if result.strip() else "Code executed successfully."
    except Exception as e:
        logger.error(f"Error executing: {str(e)}")
        return f"Error: {str(e)}"

@server.tool("execute_python")
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

@server.tool("query")
async def query_tool(
    session_id: str,
    query: str
) -> Dict[str, Any]:
    """
    Handle Python queries (alias for execute_python).
    """
    return await execute_python_tool(session_id, query)

@server.tool("health")
async def health_tool() -> Dict[str, Any]:
    """
    Check the health of the Python MCP server.
    """
    try:
        return {
            "reply": "Python MCP server is healthy",
            "intent": "health_check",
            "success": True,
            "status": "healthy"
        }
    except Exception as e:
        logger.error(f"Error in health_tool: {str(e)}")
        return {
            "reply": f"Python MCP server health check failed: {str(e)}",
            "intent": "health_check",
            "success": False,
            "status": "unhealthy"
        }

@server.tool("validate_code")
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

if __name__ == "__main__":
    logger.info("Starting Python MCP Server (FastMCP)...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8003")))
