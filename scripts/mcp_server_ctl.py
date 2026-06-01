"""MCP server control script — reliable start/stop/status for Windows."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

PID_FILE = Path.home() / ".designdoc_mcp" / "server.pid"
LOG_FILE = Path("logs/server.log")
TRANSPORT = os.environ.get("DESIGNDOC_TRANSPORT", "streamable-http")
HOST = os.environ.get("DESIGNDOC_HOST", "0.0.0.0")
PORT = int(os.environ.get("DESIGNDOC_PORT", "8765"))


def _is_running(pid: int) -> bool:
    """Check whether a Windows process is still alive."""
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True,
        text=True,
    )
    return str(pid) in result.stdout


def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except ValueError:
        return None


def _write_pid(pid: int) -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid))


def _remove_pid() -> None:
    PID_FILE.unlink(missing_ok=True)


def start() -> None:
    """Start the MCP server and record its PID."""
    pid = _read_pid()
    if pid and _is_running(pid):
        print(f"Server already running (PID {pid}).")
        return

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "designdoc_mcp.server",
            "--transport",
            TRANSPORT,
            "--host",
            HOST,
            "--port",
            str(PORT),
        ],
        stdout=open(LOG_FILE, "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    )
    _write_pid(proc.pid)
    print(f"Server started (PID {proc.pid}, port {PORT}).")


def _wait_for_port_free(timeout: float = 10.0) -> bool:
    """Wait until the configured port is no longer bound."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
        )
        if f":{PORT}" not in result.stdout:
            return True
        time.sleep(0.5)
    return False


def stop() -> None:
    """Stop the MCP server gracefully using the recorded PID."""
    pid = _read_pid()
    if pid is None:
        print("PID file not found. Server may not be running.")
        return

    if not _is_running(pid):
        print(f"Server not running (stale PID {pid}).")
        _remove_pid()
        return

    # Graceful shutdown: taskkill sends WM_CLOSE to the specific process.
    # Avoid os.kill(pid, 2) on Windows — it broadcasts Ctrl+C to the entire
    # console group and can kill the newly-started server during restart().
    subprocess.run(
        ["taskkill", "/PID", str(pid)],
        capture_output=True,
    )

    # Wait up to 5 seconds for graceful exit
    for _ in range(10):
        if not _is_running(pid):
            break
        time.sleep(0.5)
    else:
        # Force kill if still alive
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        time.sleep(0.5)

    _remove_pid()
    if _is_running(pid):
        print(f"Server force-killed (PID {pid}).")
    else:
        print(f"Server stopped (PID {pid}).")


def status() -> None:
    """Report whether the server is running."""
    pid = _read_pid()
    if pid is None:
        print("Server not running (no PID file).")
        return
    if _is_running(pid):
        print(f"Server running (PID {pid}, port {PORT}).")
    else:
        print(f"Server not running (stale PID {pid}).")


def restart() -> None:
    stop()
    # Ensure the old process has released the port before starting a new one.
    # On Windows the port can linger for a few seconds after the process exits.
    if not _wait_for_port_free(timeout=10.0):
        print(f"Warning: port {PORT} still appears bound after stop.")
    start()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "restart":
        restart()
    elif cmd == "status":
        status()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python scripts/mcp_server_ctl.py [start|stop|restart|status]")
