"""Python agent: extracts code from a message and runs it in the sandbox (see sandbox_runner.py)."""
import ast
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, Optional

from core import config
from core.agents import sandbox_runner

AGENT = "python"
RUNNER = Path(__file__).with_name("sandbox_runner.py")

_FENCE_RE = re.compile(r"```[ \t]*(?:python|py|python3)?[ \t]*\n?(.*?)```", re.DOTALL | re.IGNORECASE)
_INSTRUCTION_RE = re.compile(
    r"^\s*(?:please\s+)?(?:can you\s+|could you\s+)?(?:execute|run|evaluate|eval|test)\s+"
    r"(?:this|the following|my|the|some)?\s*(?:python3?\s*)?(?:code|script|snippet|program|expression)?"
    r"\s*(?:for me)?\s*(?:please)?\s*[:\-]?",
    re.IGNORECASE,
)
_RUN_REQUEST_RE = re.compile(
    r"^\s*(?:please\s+)?(?:can you\s+|could you\s+)?(?:execute|run|evaluate|eval)\b[^\n]*\b(?:code|python|script|snippet|program)\b",
    re.IGNORECASE,
)
_CODE_MARKERS = ("print(", "import ", "def ", "class ", "=", "lambda", "for ", "while ", "return ")


def _parses(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def looks_like_code(query: str) -> bool:
    """True when a message is (or asks to run) Python code rather than talking about it."""
    if "```" in query or _RUN_REQUEST_RE.search(query):
        return True
    stripped = query.strip()
    if stripped.endswith("?") or not _parses(stripped):
        return False
    return "\n" in stripped or any(marker in stripped for marker in _CODE_MARKERS)


def extract_code(query: str) -> str:
    fenced = _FENCE_RE.findall(query)
    if fenced:
        return "\n\n".join(textwrap.dedent(block).strip() for block in fenced)
    text = _INSTRUCTION_RE.sub("", query, count=1).strip()
    if text.startswith("[") and text.endswith("]") and not _parses(text):
        text = text[1:-1].strip()
    text = textwrap.dedent(text).strip()
    if _parses(text):
        return text
    # Drop leading prose lines ("Here is my code:") until the rest parses.
    lines = text.splitlines()
    for start in range(1, min(len(lines), 4)):
        candidate = textwrap.dedent("\n".join(lines[start:])).strip()
        if candidate and _parses(candidate):
            return candidate
    return text


def _limit_resources() -> None:  # pragma: no cover - POSIX only
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))


def run_code(code: str) -> Dict[str, Any]:
    """Run code in an isolated child interpreter. Returns stdout, stderr, exit status."""
    try:
        problems = sandbox_runner.validate(code)
    except SyntaxError as e:
        return {"ok": False, "stdout": "", "stderr": f"SyntaxError: {e.msg} (line {e.lineno})", "timed_out": False}
    if problems:
        return {"ok": False, "stdout": "", "stderr": "Blocked by sandbox:\n" + "\n".join(f"  - {p}" for p in problems), "timed_out": False}

    # Minimal environment: no API keys or other secrets reach user code.
    env = {"PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0"}
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    kwargs: Dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["preexec_fn"] = _limit_resources

    with tempfile.TemporaryDirectory(prefix="sandbox-") as workdir:
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(RUNNER)],
                input=code.encode("utf-8"),
                capture_output=True,
                timeout=config.PYTHON_TIMEOUT,
                cwd=workdir,
                env=env,
                **kwargs,
            )
        except subprocess.TimeoutExpired as e:
            stdout = (e.stdout or b"").decode("utf-8", "replace")
            return {"ok": False, "stdout": stdout, "stderr": f"Timed out after {config.PYTHON_TIMEOUT} seconds.", "timed_out": True}

    limit = config.PYTHON_MAX_OUTPUT
    stdout = proc.stdout.decode("utf-8", "replace")
    stderr = proc.stderr.decode("utf-8", "replace")
    if len(stdout) > limit:
        stdout = stdout[:limit] + f"\n... (output truncated at {limit} characters)"
    return {"ok": proc.returncode == 0, "stdout": stdout, "stderr": stderr[-limit:], "timed_out": False}


def format_result(result: Dict[str, Any]) -> str:
    parts = []
    if result["stdout"].strip():
        parts.append("**Output:**\n```text\n" + result["stdout"].rstrip() + "\n```")
    if result["stderr"].strip():
        parts.append("**Error:**\n```text\n" + result["stderr"].rstrip() + "\n```")
    if not parts:
        parts.append("Code ran successfully with no output. (Use `print()` to show values.)")
    return "\n\n".join(parts)


def handle(session_id: str, query: str, code: Optional[str] = None) -> Dict[str, Any]:
    code = (code or extract_code(query)).strip()
    if not code:
        return {"success": False, "agent": AGENT, "reply": "Please include the Python code you want me to run."}
    if re.search(r"\binput\s*\(", code):
        return {
            "success": False,
            "agent": AGENT,
            "reply": "Interactive `input()` isn't supported here. Put the values directly in the code instead.",
        }
    result = run_code(code)
    return {"success": result["ok"], "agent": AGENT, "reply": format_result(result), "code": code}


def validate(code: str) -> Dict[str, Any]:
    try:
        problems = sandbox_runner.validate(code)
    except SyntaxError as e:
        return {"valid": False, "problems": [f"SyntaxError: {e.msg} (line {e.lineno})"]}
    return {"valid": not problems, "problems": problems}


def health() -> Dict[str, Any]:
    return {"status": "healthy", "agent": AGENT, "timeout_seconds": config.PYTHON_TIMEOUT}
