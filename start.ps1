param(
    [string]$Transport = "http",
    [int]$Port = 8765,
    [string]$DataDir = "",
    [string]$ApiToken = "",
    [string]$LogDir = "",
    [string]$DeployTo = ""
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($DeployTo) {
    Write-Host "=== DesignDoc MCP - Deploy & Start ===" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Target: $DeployTo" -ForegroundColor Yellow
    Write-Host ""

    if (-not (Test-Path $DeployTo)) {
        New-Item -ItemType Directory -Path $DeployTo -Force | Out-Null
        Write-Host "[OK] Created directory: $DeployTo" -ForegroundColor Green
    }

    $deployItems = @(
        @{ Src = ".agents\skills"; DstParent = ".agents"; Desc = "Generic skills (.agents/)" },
        @{ Src = ".claude\skills"; DstParent = ".claude"; Desc = "Claude Code skills" },
        @{ Src = ".atomcode\skills"; DstParent = ".atomcode"; Desc = "AtomCode skills" }
    )

    foreach ($item in $deployItems) {
        $srcPath = Join-Path $ProjectDir $item.Src
        $dstParent = Join-Path $DeployTo $item.DstParent
        if (Test-Path $srcPath) {
            if (-not (Test-Path $dstParent)) { New-Item -ItemType Directory -Path $dstParent -Force | Out-Null }
            Copy-Item -Path $srcPath -Destination $dstParent -Recurse -Force
            Write-Host "[OK] $($item.Desc)" -ForegroundColor Green
        }
    }

    # MCP 配置文件：Claude Code 使用根目录 .mcp.json，Cursor 使用 .cursor/mcp.json，Trae 使用 .trae/mcp.json
    $mcpConfigHTTP = "{`n  `"mcpServers`": {`n    `"designdoc`": {`n      `"type`": `"http`",`n      `"url`": `"http://localhost:${Port}/mcp`"`n    }`n  }`n}"
    $mcpConfigs = @(
        @{ Path = ".cursor\mcp.json"; Config = $mcpConfigHTTP; Desc = "Cursor MCP config (Streamable HTTP)" },
        @{ Path = ".trae\mcp.json"; Config = $mcpConfigHTTP; Desc = "Trae MCP config (Streamable HTTP)" },
        @{ Path = ".mcp.json"; Config = $mcpConfigHTTP; Desc = "Claude Code / Generic MCP config (Streamable HTTP)" }
    )

    foreach ($cfg in $mcpConfigs) {
        $cfgPath = Join-Path $DeployTo $cfg.Path
        $cfgDir = Split-Path -Parent $cfgPath
        if (-not (Test-Path $cfgDir)) { New-Item -ItemType Directory -Path $cfgDir -Force | Out-Null }
        Set-Content -Path $cfgPath -Value $cfg.Config -Encoding UTF8
        Write-Host "[OK] $($cfg.Desc) -> $($cfg.Path)" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "Deploy complete! Now starting server..." -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "=== DesignDoc MCP Server Setup ===" -ForegroundColor Cyan

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] uv not found. Install from https://docs.astral.sh/uv/" -ForegroundColor Red
    exit 1
}

Write-Host "[1/5] Installing dependencies..." -ForegroundColor Yellow
uv sync --directory $ProjectDir
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Dependency install failed" -ForegroundColor Red; exit 1 }

# 数据目录：DeployTo 时默认为部署目标目录下的 data/ 子目录
if ($DataDir) {
    $env:DESIGNDOC_DATA_DIR = $DataDir
    Write-Host "[2/5] Data directory: $DataDir" -ForegroundColor Green
} elseif ($DeployTo) {
    $DeployDataDir = Join-Path $DeployTo "data"
    $env:DESIGNDOC_DATA_DIR = $DeployDataDir
    Write-Host "[2/5] Data directory: $DeployDataDir (deploy target)" -ForegroundColor Green
} else {
    $DefaultDir = Join-Path $env:USERPROFILE ".designdoc_mcp"
    Write-Host "[2/5] Data directory: $DefaultDir (default)" -ForegroundColor Green
}

if ($ApiToken) {
    $env:DESIGNDOC_API_TOKEN = $ApiToken
    Write-Host "[3/5] API token: configured" -ForegroundColor Green
} else {
    Write-Host "[3/5] API token: not set (open access)" -ForegroundColor Yellow
}

if ($LogDir) {
    $env:DESIGNDOC_LOG_DIR = $LogDir
    Write-Host "[4/5] Log directory: $LogDir" -ForegroundColor Green
} elseif ($DeployTo) {
    $DeployLogDir = Join-Path $DeployTo "logs"
    $env:DESIGNDOC_LOG_DIR = $DeployLogDir
    Write-Host "[4/5] Log directory: $DeployLogDir (deploy target)" -ForegroundColor Green
} else {
    Write-Host "[4/5] Log directory: auto (logs/ under project dir)" -ForegroundColor Yellow
}

Write-Host "[5/5] Starting server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Transport: $Transport" -ForegroundColor Cyan
Write-Host "  Port:      $Port" -ForegroundColor Cyan
Write-Host "  Web UI:    http://localhost:$Port" -ForegroundColor Cyan
Write-Host "  MCP HTTP:  http://localhost:$Port/mcp" -ForegroundColor Cyan
if ($DeployTo) {
    Write-Host "  Deploy to: $DeployTo" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Next: Open '$DeployTo' in your IDE, agents will auto-discover skills & MCP" -ForegroundColor Yellow
}
Write-Host ""

$env:DESIGNDOC_TRANSPORT = $Transport
$env:DESIGNDOC_PORT = $Port.ToString()

uv run --directory $ProjectDir designdoc-mcp --transport $Transport --port $Port
