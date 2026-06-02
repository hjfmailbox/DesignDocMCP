#!/usr/bin/env bash
# probe_inspect.sh — MiniDebateRuntime ops toolkit
# Usage: probe_inspect.sh [report|timeline|session <id>|logs|status|purge|help]

set -e

OUTPUT_DIR="${PROBE_OUTPUTS_DIR:-E:/DesignDocMCPTest1/probe_outputs}"
LOGS_DIR="${PROBE_LOGS_DIR:-logs}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

jsonval() {
    sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$1" | head -1
}

server_pid() {
    tasklist 2>/dev/null | grep -i "mini-debate" | awk '{print $2}' || true
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_report() {
    echo "========================================"
    echo "  Session Report"
    echo "========================================"
    echo ""

    local dirs
    dirs=$(ls -1td "$OUTPUT_DIR"/sess_* 2>/dev/null || true)
    if [ -z "$dirs" ]; then
        echo "No sessions found."
        return
    fi

    printf "%-24s %-22s %-22s %-8s %-8s\n" "Session" "Agent" "Model" "Result" "Phases"
    printf "%-24s %-22s %-22s %-8s %-8s\n" "------------------------" "----------------------" "----------------------" "--------" "--------"

    for dir in $dirs; do
        local sid report
        sid=$(basename "$dir")
        report="$dir/report.json"
        [ ! -f "$report" ] && continue

        local agent model result p
        agent=$(jsonval "$report" agent)
        model=$(jsonval "$report" model)
        result=$(jsonval "$report" result)

        p=0
        grep -q '"proposal"[[:space:]]*:[[:space:]]*true'  "$report" && p=$((p+1))
        grep -q '"challenge"[[:space:]]*:[[:space:]]*true' "$report" && p=$((p+1))
        grep -q '"revision"[[:space:]]*:[[:space:]]*true'  "$report" && p=$((p+1))
        grep -q '"consensus"[[:space:]]*:[[:space:]]*true' "$report" && p=$((p+1))

        printf "%-24s %-22s %-22s %-8s %-8s\n" "$sid" "$agent" "$model" "$result" "$p/4"
    done
}

cmd_timeline() {
    local n=${1:-10}
    echo "========================================"
    echo "  Recent Timeline (last $n)"
    echo "========================================"

    if [ ! -f "$LOGS_DIR/session_timeline.jsonl" ]; then
        echo "No timeline logs."
        return
    fi

    tail -"$n" "$LOGS_DIR/session_timeline.jsonl" | while read -r line; do
        local ev ph sid tid
        ev=$(echo  "$line" | sed -n 's/.*"event"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        ph=$(echo  "$line" | sed -n 's/.*"phase"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        sid=$(echo "$line" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        tid=$(echo "$line" | sed -n 's/.*"task_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        if [ -n "$tid" ]; then
            printf "  %-18s %-10s %-26s %s\n" "$ev" "$ph" "$sid" "$tid"
        else
            printf "  %-18s %-10s %-26s\n" "$ev" "$ph" "$sid"
        fi
    done
}

cmd_session() {
    local sid=$1
    if [ -z "$sid" ]; then
        echo "Usage: probe_inspect.sh session <session_id>"
        exit 1
    fi

    local report="$OUTPUT_DIR/$sid/report.json"
    if [ ! -f "$report" ]; then
        echo "Session $sid not found."
        exit 1
    fi

    echo "========================================"
    echo "  Session: $sid"
    echo "========================================"
    cat "$report" | sed 's/^/  /'
    echo ""

    echo "--- Timeline ---"
    grep "\"session_id\":\"$sid\"" "$LOGS_DIR/session_timeline.jsonl" 2>/dev/null | while read -r line; do
        local ev ph tid
        ev=$(echo "$line" | sed -n 's/.*"event"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        ph=$(echo "$line" | sed -n 's/.*"phase"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        tid=$(echo "$line" | sed -n 's/.*"task_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        if [ -n "$tid" ]; then
            printf "  %-18s %-10s %s\n" "$ev" "$ph" "$tid"
        else
            printf "  %-18s %-10s\n" "$ev" "$ph"
        fi
    done || true

    echo ""
    echo "--- Responses ---"
    grep "\"session_id\":\"$sid\"" "$LOGS_DIR/responses.jsonl" 2>/dev/null | while read -r line; do
        local ag ph st
        ag=$(echo "$line" | sed -n 's/.*"agent_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        ph=$(echo "$line" | sed -n 's/.*"phase"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        st=$(echo "$line" | sed -n 's/.*"status"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        printf "  %-10s %-12s %s\n" "$ph" "$st" "$ag"
    done || true
}

cmd_logs() {
    echo "========================================"
    echo "  Log Files"
    echo "========================================"
    for f in "$LOGS_DIR"/*.jsonl; do
        [ -f "$f" ] || continue
        local name lines
        name=$(basename "$f")
        lines=$(wc -l < "$f" | tr -d ' ')
        printf "  %-30s %5s lines\n" "$name" "$lines"
    done
}

cmd_status() {
    echo "========================================"
    echo "  Server Status"
    echo "========================================"
    local pid
    pid=$(server_pid)
    if [ -n "$pid" ]; then
        echo "  Status: RUNNING"
        echo "  PID:    $pid"
    else
        echo "  Status: NOT RUNNING"
    fi
    echo ""
    echo "  Output dir: $OUTPUT_DIR"
    echo "  Logs dir:   $LOGS_DIR"
    echo ""
    local count
    count=$(ls -1d "$OUTPUT_DIR"/sess_* 2>/dev/null | wc -l | tr -d ' ')
    echo "  Sessions:   $count"
}

# ---------------------------------------------------------------------------
# Reserved ops commands (not implemented yet)
# ---------------------------------------------------------------------------

cmd_purge() {
    echo "========================================"
    echo "  Purge Session (RESERVED)"
    echo "========================================"
    echo ""
    echo "This command is reserved for future implementation."
    echo "Planned sub-commands:"
    echo "  purge session <id>   — remove single session files"
    echo "  purge all           — clear all sessions and logs"
    echo "  purge completed     — remove only COMPLETE sessions"
    echo ""
    echo "No action taken."
}

# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

usage() {
    cat <<EOF
MiniDebateRuntime ops toolkit

Usage: probe_inspect.sh <command> [args]

Commands:
  report                Show all session summary (default)
  timeline [n]          Show last n timeline events (default 10)
  session <id>          Show detail for a single session
  logs                  Show log file statistics
  status                Show server and directory status
  purge                 Reserved — session cleanup (not implemented)
  help                  Show this help

Environment:
  PROBE_OUTPUTS_DIR     Output directory (default: E:/DesignDocMCPTest1/probe_outputs)
  PROBE_LOGS_DIR        Logs directory (default: logs)
EOF
}

main() {
    case "${1:-report}" in
        report|"")   cmd_report ;;
        timeline)    cmd_timeline "${2:-10}" ;;
        session)     cmd_session "$2" ;;
        logs)        cmd_logs ;;
        status)      cmd_status ;;
        purge)       cmd_purge ;;
        help|--help|-h) usage ;;
        *)           echo "Unknown command: $1"; usage; exit 1 ;;
    esac
}

main "$@"
