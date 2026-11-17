"""Process helpers for the launcher scripts: start children, prefix their output, wait for ports, stop cleanly."""
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List

ROOT_DIR = Path(__file__).resolve().parent.parent


class ProcessGroup:
    def __init__(self):
        self.processes: List[tuple] = []

    def start(self, name: str, args: List[str], env: dict = None, cwd: Path = ROOT_DIR) -> subprocess.Popen:
        child_env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8", **(env or {})}
        proc = subprocess.Popen(
            args, cwd=cwd, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        threading.Thread(target=self._pipe, args=(name, proc), daemon=True).start()
        self.processes.append((name, proc))
        return proc

    @staticmethod
    def _pipe(name: str, proc: subprocess.Popen) -> None:
        for line in proc.stdout:
            sys.stdout.write(f"[{name}] {line}")
            sys.stdout.flush()

    def wait_for_port(self, name: str, port: int, timeout: float = 300) -> bool:
        """Wait until something listens on the port, failing early if the process exits."""
        proc = dict(self.processes)[name]
        deadline = time.time() + timeout
        while time.time() < deadline:
            if proc.poll() is not None:
                print(f"!! {name} exited with code {proc.returncode}")
                return False
            with socket.socket() as s:
                s.settimeout(1)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return True
            time.sleep(0.5)
        print(f"!! {name} did not open port {port} within {timeout:.0f}s")
        return False

    def wait(self) -> None:
        """Block until any child exits or Ctrl+C."""
        try:
            while all(proc.poll() is None for _, proc in self.processes):
                time.sleep(1)
            for name, proc in self.processes:
                if proc.poll() is not None:
                    print(f"!! {name} exited with code {proc.returncode}; shutting down.")
        except KeyboardInterrupt:
            print("\nShutting down...")

    def stop(self) -> None:
        for name, proc in reversed(self.processes):
            if proc.poll() is None:
                proc.terminate()
        for name, proc in self.processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


FRONTEND_DIR = ROOT_DIR / "frontend"
WEB_DEV_PORT = 5173


def start_web_dev(group: ProcessGroup) -> bool:
    """Start the React frontend's Vite dev server (it proxies /api to the gateway)."""
    npm = shutil.which("npm")
    if not npm:
        print("!! npm not found. Install Node.js 20+ to run the web UI.")
        return False
    if not (FRONTEND_DIR / "node_modules").is_dir():
        print("Installing frontend dependencies (first run)...")
        if subprocess.run([npm, "install"], cwd=FRONTEND_DIR).returncode != 0:
            print("!! npm install failed")
            return False
    group.start("web", [npm, "run", "dev", "--", "--port", str(WEB_DEV_PORT), "--strictPort"], cwd=FRONTEND_DIR)
    if not group.wait_for_port("web", WEB_DEV_PORT, timeout=60):
        return False
    print(f"OK web UI: http://localhost:{WEB_DEV_PORT}")
    return True
