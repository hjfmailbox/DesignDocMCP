#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DEPLOY_TO=""
TRANSPORT="http"
PORT=8765
DATA_DIR=""
API_TOKEN=""
LOG_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --deploy-to) DEPLOY_TO="$2"; shift 2 ;;
        --transport) TRANSPORT="$2"; shift 2 ;;
        --port) PORT="$2"; shift 2 ;;
        --data-dir) DATA_DIR="$2"; shift 2 ;;
        --api-token) API_TOKEN="$2"; shift 2 ;;
        --log-dir) LOG_DIR="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -n "$DEPLOY_TO" ]]; then
    echo "=== DesignDoc MCP - Deploy & Start ==="
    echo ""
    echo "Target: $DEPLOY_TO"
    echo ""

    if [[ ! -d "$DEPLOY_TO" ]]; then
        mkdir -p "$DEPLOY_TO"
        echo "[OK] Created directory: $DEPLOY_TO"
    fi

    MCP_URL="http://localhost:${PORT}/mcp"

    for skill_dir in .agents/skills .claude/skills .atomcode/skills; do
        src_path="$SCRIPT_DIR/$skill_dir"
        dst_parent="$DEPLOY_TO/$(dirname "$skill_dir")"
        if [[ -d "$src_path" ]]; then
            mkdir -p "$dst_parent"
            cp -r "$src_path" "$dst_parent/"
            echo "[OK] $skill_dir"
        fi
    done

    mkdir -p "$DEPLOY_TO/.cursor"
    cat > "$DEPLOY_TO/.cursor/mcp.json" << EOF
{
  "mcpServers": {
    "designdoc": {
      "url": "$MCP_URL"
    }
  }
}
EOF
    echo "[OK] .cursor/mcp.json"

    mkdir -p "$DEPLOY_TO/.trae"
    cat > "$DEPLOY_TO/.trae/mcp.json" << EOF
{
    "mcpServers":  {
                       "designdoc":  {
                                         "url":  "$MCP_URL"
                                     }
                   }
}
EOF
    echo "[OK] .trae/mcp.json"

    cat > "$DEPLOY_TO/.mcp.json" << EOF
{
  "mcpServers": {
    "designdoc": {
      "url": "$MCP_URL"
    }
  }
}
EOF
    echo "[OK] .mcp.json"

    echo ""
    echo "Deploy complete! Now starting server..."
    echo ""
fi

cd "$SCRIPT_DIR"

if [[ -n "$DATA_DIR" ]]; then
    export DESIGNDOC_DATA_DIR="$DATA_DIR"
else
    DATA_DIR="$SCRIPT_DIR/data"
    mkdir -p "$DATA_DIR"
    export DESIGNDOC_DATA_DIR="$DATA_DIR"
fi

if [[ -n "$API_TOKEN" ]]; then
    export DESIGNDOC_API_TOKEN="$API_TOKEN"
fi

if [[ -n "$LOG_DIR" ]]; then
    export DESIGNDOC_LOG_DIR="$LOG_DIR"
fi

export DESIGNDOC_TRANSPORT="$TRANSPORT"
export DESIGNDOC_HOST="0.0.0.0"
export DESIGNDOC_PORT="$PORT"

echo "=== DesignDoc MCP Server ==="
echo "Transport:  $TRANSPORT"
echo "Host:       $DESIGNDOC_HOST"
echo "Port:       $PORT"
echo "Data dir:   $DATA_DIR"
echo ""
echo "Connect your agents to: http://localhost:$PORT/mcp"
if [[ -n "$DEPLOY_TO" ]]; then
    echo "Deploy to:  $DEPLOY_TO"
    echo ""
    echo "Next: Open '$DEPLOY_TO' in your IDE, agents will auto-discover skills & MCP"
fi
echo "Starting server..."

uv run designdoc-mcp --transport "$TRANSPORT" --host "$DESIGNDOC_HOST" --port "$PORT"
