"""Hybrid MCP server control script — manages Python API + Go gateway on Windows."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

RUN_DIR = Path.home() / ".designdoc_mcp"
API_PID_FILE = RUN_DIR / "api.pid"
GW_PID_FILE = RUN_DIR / "gateway.pid"
API_LOG_FILE = Path("logs/api_server.log")
GW_LOG_FILE = Path("logs/gateway.log")
TRANSPORT = os.environ.get("DESIGNDOC_TRANSPORT", "streamable-http")
HOST = os.environ.get("DESIGNDOC_HOST", "0.0.0.0")
PORT = int(os.environ.get("DESIGNDOC_PORT", "8765"))
API_PORT = int(os.environ.get("DESIGNDOC_API_PORT", "9000"))


def _is_running(pid: int) -> bool:
    """Check whether a Windows process is still alive."""
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True,
        text=True,
    )
    return str(pid) in result.stdout


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip())
    except ValueError:
        return None


def _write_pid(path: Path, pid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid))


def _remove_pid(path: Path) -> None:
    path.unlink(missing_ok=True)


def _kill(pid: int, force: bool = False) -> None:
    cmd = ["taskkill", "/PID", str(pid)]
    if force:
        cmd.append("/F")
    subprocess.run(cmd, capture_output=True)


def _wait_for_api(timeout: float = 15.0) -> bool:
    """Poll until the Python API is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["curl", "-sf", f"http://127.0.0.1:{API_PORT}/api/v1/list_sessions"],
            capture_output=True,
        )
        if result.returncode == 0:
            return True
        time.sleep(0.5)
    return False


def _wait_for_port_free(port: int, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
        )
        if f":{port}" not in result.stdout:
            return True
        time.sleep(0.5)
    return False


def start_api() -> int | None:
    """Start the Python Engine API server."""
    pid = _read_pid(API_PID_FILE)
    if pid and _is_running(pid):
        print(f"API server already running (PID {pid}).")
        return pid

    API_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["DESIGNDOC_API_PORT"] = str(API_PORT)

    proc = subprocess.Popen(
        [sys.executable, "-m", "designdoc_mcp.api_server"],
        stdout=open(API_LOG_FILE, "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        env=env,
    )
    _write_pid(API_PID_FILE, proc.pid)
    print(f"API server started (PID {proc.pid}, port {API_PORT}).")
    return proc.pid


def start_gateway() -> int | None:
    """Start the Go MCP gateway."""
    pid = _read_pid(GW_PID_FILE)
    if pid and _is_running(pid):
        print(f"Gateway already running (PID {pid}).")
        return pid

    GW_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Locate the compiled binary relative to script location
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    gw_binary = repo_root / "mcp-gateway.exe"
    if not gw_binary.exists():
        # Fallback: search in GOPATH or PATH
        gw_binary = Path("mcp-gateway.exe")

    proc = subprocess.Popen(
        [
            str(gw_binary),
            "-transport", TRANSPORT,
            "-host", HOST,
            "-port", str(PORT),
            "-api-base-url", f"http://127.0.0.1:{API_PORT}",
        ],
        stdout=open(GW_LOG_FILE, "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    )
    _write_pid(GW_PID_FILE, proc.pid)
    print(f"MCP gateway started (PID {proc.pid}, port {PORT}, transport={TRANSPORT}).")
    return proc.pid


def stop_api() -> None:
    """Stop the Python API server."""
    pid = _read_pid(API_PID_FILE)
    if pid is None:
        print("API server not running (no PID file).")
        return
    if not _is_running(pid):
        print(f"API server not running (stale PID {pid}).")
        _remove_pid(API_PID_FILE)
        return

    _kill(pid)
    for _ in range(10):
        if not _is_running(pid):
            break
        time.sleep(0.5)
    else:
        _kill(pid, force=True)
        time.sleep(0.5)

    _remove_pid(API_PID_FILE)
    print(f"API server stopped (PID {pid}).")


def stop_gateway() -> None:
    """Stop the Go MCP gateway."""
    pid = _read_pid(GW_PID_FILE)
    if pid is None:
        print("Gateway not running (no PID file).")
        return
    if not _is_running(pid):
        print(f"Gateway not running (stale PID {pid}).")
        _remove_pid(GW_PID_FILE)
        return

    _kill(pid)
    for _ in range(10):
        if not _is_running(pid):
            break
        time.sleep(0.5)
    else:
        _kill(pid, force=True)
        time.sleep(0.5)

    _remove_pid(GW_PID_FILE)
    print(f"Gateway stopped (PID {pid}).")


def status() -> None:
    """Report status of both processes."""
    api_pid = _read_pid(API_PID_FILE)
    gw_pid = _read_pid(GW_PID_FILE)

    api_status = "running" if (api_pid and _is_running(api_pid)) else "stopped"
    gw_status = "running" if (gw_pid and _is_running(gw_pid)) else "stopped"

    print(f"API server: {api_status}" + (f" (PID {api_pid}, port {API_PORT})" if api_pid else ""))
    print(f"Gateway:    {gw_status}" + (f" (PID {gw_pid}, port {PORT})" if gw_pid else ""))


def start() -> None:
    """Start both API and gateway."""
    start_api()
    print("Waiting for API to be ready...")
    if not _wait_for_api(timeout=15.0):
        print("Warning: API did not respond in time. Gateway may fail to connect.")
    start_gateway()


def stop() -> None:
    """Stop gateway first, then API."""
    stop_gateway()
    stop_api()


def restart() -> None:
    stop()
    _wait_for_port_free(PORT, timeout=10.0)
    _wait_for_port_free(API_PORT, timeout=10.0)
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
