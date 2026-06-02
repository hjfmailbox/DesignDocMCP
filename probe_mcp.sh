#!/usr/bin/env bash
# probe_mcp.sh — MiniDebateRuntime lifecycle & ops toolkit
# Usage: probe_mcp.sh <cmd>
#
# Commands:
#   start    Start the server if not running
#   stop     Graceful stop (SIGTERM), fallback to force after 5s
#   restart  stop + start
#   purge    stop + clear outputs + clear logs + start
#   status   Show process and session state
#

set -e

OUTPUT_DIR="${PROBE_OUTPUTS_DIR:-E:/DesignDocMCPTest1/probe_outputs}"
LOGS_DIR="${PROBE_LOGS_DIR:-logs}"
BINARY="./mini-debate-runtime.exe"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

server_pid() {
    tasklist 2>/dev/null | grep -i "mini-debate-runtime" | awk '{print $2}' || true
}

is_running() {
    local pid
    pid=$(server_pid)
    [ -n "$pid" ]
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_start() {
    if is_running; then
        echo "Server already running (PID $(server_pid))"
        return
    fi
    if [ ! -f "$BINARY" ]; then
        echo "Binary not found: $BINARY"
        exit 1
    fi
    powershell -Command "Start-Process -FilePath '$BINARY' -WindowStyle Hidden"
    sleep 2
    if is_running; then
        echo "Server started (PID $(server_pid))"
    else
        echo "Failed to start server"
        exit 1
    fi
}

cmd_stop() {
    local pid
    pid=$(server_pid)
    if [ -z "$pid" ]; then
        echo "Server not running"
        return
    fi

    echo "Stopping server (PID $pid) — sending graceful termination..."
    # Step 1: attempt graceful (SIGTERM via taskkill //IM)
    taskkill //IM mini-debate-runtime.exe >/dev/null 2>&1 || true

    # Step 2: wait up to 5s for process to exit
    for i in 1 2 3 4 5; do
        sleep 1
        pid=$(server_pid)
        if [ -z "$pid" ]; then
            echo "Server stopped gracefully."
            return
        fi
    done

    # Step 3: force kill if still running
    echo "Graceful stop timed out. Force killing..."
    taskkill //F //IM mini-debate-runtime.exe >/dev/null 2>&1 || true
    sleep 1
    pid=$(server_pid)
    if [ -z "$pid" ]; then
        echo "Server stopped (force)."
    else
        echo "WARNING: server still running (PID $pid)"
    fi
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_purge() {
    cmd_stop
    echo "Clearing outputs ($OUTPUT_DIR)..."
    rm -rf "$OUTPUT_DIR"/* 2>/dev/null || true
    echo "Clearing logs ($LOGS_DIR)..."
    rm -f "$LOGS_DIR"/* 2>/dev/null || true
    cmd_start
    echo "Purge complete. Server running fresh (PID $(server_pid))."
}

cmd_status() {
    local pid
    pid=$(server_pid)
    if [ -n "$pid" ]; then
        echo "Server: RUNNING (PID $pid)"
    else
        echo "Server: STOPPED"
    fi
    local count
    count=$(ls -1d "$OUTPUT_DIR"/sess_* 2>/dev/null | wc -l | tr -d ' ')
    echo "Sessions (disk): $count"
}

# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

usage() {
    cat <<EOF
MiniDebateRuntime lifecycle toolkit

Usage: probe_mcp.sh <command>

Commands:
  start     Start the server (if not running)
  stop      Graceful stop, fallback to force after 5s
  restart   stop + start
  purge     Full reset: stop + clear outputs/logs + start
  status    Show process and session state

Environment:
  PROBE_OUTPUTS_DIR   Output directory (default: E:/DesignDocMCPTest1/probe_outputs)
  PROBE_LOGS_DIR      Logs directory (default: logs)
EOF
}

main() {
    case "${1:-status}" in
        start)    cmd_start ;;
        stop)     cmd_stop ;;
        restart)  cmd_restart ;;
        purge)    cmd_purge ;;
        status)   cmd_status ;;
        help|--help|-h) usage ;;
        *)        echo "Unknown command: $1"; usage; exit 1 ;;
    esac
}

main "$@"
