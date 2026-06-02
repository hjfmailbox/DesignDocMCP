"""Verify MCP tools/list returns valid schemas with array required fields."""
import json
import urllib.request

# Step 1: Establish SSE session
req = urllib.request.Request("http://127.0.0.1:8765/sse")
resp = urllib.request.urlopen(req, timeout=5)
endpoint = None
for _ in range(5):
    line = resp.readline().decode().strip()
    if line.startswith("event: endpoint"):
        data = resp.readline().decode().strip()
        endpoint = data.split("data: ")[1]
        break

if not endpoint:
    raise RuntimeError("No SSE endpoint received")

print(f"SSE session: {endpoint}")

post_url = "http://127.0.0.1:8765" + endpoint

def send_request(payload: dict) -> None:
    r = urllib.request.Request(
        post_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(r)

def read_response() -> dict:
    """Read the next JSON-RPC response from the SSE stream."""
    while True:
        line = resp.readline().decode().strip()
        if line.startswith("event: message"):
            data_line = resp.readline().decode().strip()
            if data_line.startswith("data: "):
                return json.loads(data_line[6:])
        if not line:
            continue

# Step 2: Initialize
send_request({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"},
    },
})
init_data = read_response()
print("Initialize:", "ok" if "result" in init_data else "failed")

# Step 3: Send initialized notification
send_request({"jsonrpc": "2.0", "method": "notifications/initialized"})

# Step 4: tools/list
send_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
tools_data = read_response()
tools = tools_data.get("result", {}).get("tools", [])

print(f"Tools count: {len(tools)}")

errors = []
for i, tool in enumerate(tools):
    schema = tool.get("inputSchema", {})
    required = schema.get("required")
    if required is None:
        errors.append(f"  tools[{i}] '{tool['name']}': required is null")
    elif not isinstance(required, list):
        errors.append(f"  tools[{i}] '{tool['name']}': required is {type(required).__name__}, expected array")

if errors:
    print("ERRORS:")
    for e in errors:
        print(e)
    exit(1)
else:
    print("All tools have valid required arrays.")
