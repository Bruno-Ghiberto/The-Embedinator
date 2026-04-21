#Requires -Version 5.1
<#
.SYNOPSIS
    Single-command launcher for The Embedinator on Windows.

.DESCRIPTION
    Starts, stops, and manages The Embedinator Docker Compose stack.
    Implements identical logic to embedinator.sh with PowerShell-native syntax.

.PARAMETER Dev
    Start with dev overlay (hot reload).

.PARAMETER Stop
    Stop all running services.

.PARAMETER Restart
    Stop then start all services.

.PARAMETER Logs
    Stream logs. Optionally specify a service name (qdrant|ollama|backend|frontend).

.PARAMETER Status
    Show health status of all services.

.PARAMETER Open
    Open the application in the default browser after startup.

.PARAMETER Help
    Show this help message.

.PARAMETER FrontendPort
    Override frontend host port for this run (default: 3000).

.PARAMETER BackendPort
    Override backend host port for this run (default: 8000).

.EXAMPLE
    .\embedinator.ps1
    .\embedinator.ps1 -Open
    .\embedinator.ps1 -Dev
    .\embedinator.ps1 -Stop
    .\embedinator.ps1 -Restart
    .\embedinator.ps1 -Logs backend
    .\embedinator.ps1 -Status
    .\embedinator.ps1 -FrontendPort 4000 -BackendPort 9000
#>

[CmdletBinding(DefaultParameterSetName = 'Start')]
param(
    [Parameter(ParameterSetName = 'Start')]
    [switch]$Dev,

    [Parameter(ParameterSetName = 'Stop')]
    [switch]$Stop,

    [Parameter(ParameterSetName = 'Restart')]
    [switch]$Restart,

    [Parameter(ParameterSetName = 'Logs')]
    [switch]$Logs,

    [Parameter(ParameterSetName = 'Logs', Position = 0)]
    [string]$LogsService = '',

    [Parameter(ParameterSetName = 'Status')]
    [switch]$Status,

    [Parameter(ParameterSetName = 'Start')]
    [switch]$Open,

    [Parameter(ParameterSetName = 'Help')]
    [switch]$Help,

    [Parameter(ParameterSetName = 'Start')]
    [Parameter(ParameterSetName = 'Restart')]
    [string]$FrontendPort = '',

    [Parameter(ParameterSetName = 'Start')]
    [Parameter(ParameterSetName = 'Restart')]
    [string]$BackendPort = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── Script root ───────────────────────────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# ── Defaults ──────────────────────────────────────────────────────────────────
$DefaultFrontendPort = '3000'
$DefaultBackendPort  = '8000'
$DefaultQdrantPort   = '6333'
$DefaultQdrantGrpc   = '6334'
$DefaultOllamaPort   = '11434'
$DefaultOllamaModels = 'qwen2.5:7b,nomic-embed-text'

$FRONTEND_PORT   = $DefaultFrontendPort
$BACKEND_PORT    = $DefaultBackendPort
$QDRANT_PORT     = $DefaultQdrantPort
$QDRANT_GRPC     = $DefaultQdrantGrpc
$OLLAMA_PORT     = $DefaultOllamaPort
$OLLAMA_MODELS   = $DefaultOllamaModels

# ── Color helpers ─────────────────────────────────────────────────────────────
function Write-Info    { param([string]$msg) Write-Host "[embedinator] $msg" -ForegroundColor Cyan }
function Write-Success { param([string]$msg) Write-Host "[embedinator] $msg" -ForegroundColor Green }
function Write-Warn    { param([string]$msg) Write-Host "[embedinator] WARNING: $msg" -ForegroundColor Yellow }
function Write-Err     { param([string]$msg) Write-Host "[embedinator] ERROR: $msg" -ForegroundColor Red }
function Die           { param([string]$msg) Write-Err $msg; exit 1 }

# ── Help ──────────────────────────────────────────────────────────────────────
function Show-Help {
    Write-Host ""
    Write-Host "The Embedinator - Launcher Script" -ForegroundColor White
    Write-Host ""
    Write-Host "USAGE" -ForegroundColor White
    Write-Host "  .\embedinator.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "SUBCOMMANDS" -ForegroundColor White
    Write-Host "  (no flags)              Start all services (first-run or resume)"
    Write-Host "  -Dev                    Start with dev overlay (hot reload)"
    Write-Host "  -Stop                   Stop all running services"
    Write-Host "  -Restart                Stop then start all services"
    Write-Host "  -Logs [SERVICE]         Stream logs (all or one: qdrant|ollama|backend|frontend)"
    Write-Host "  -Status                 Show health status of all services"
    Write-Host "  -Open                   Open the application in the default browser after startup"
    Write-Host "  -Help                   Show this help message"
    Write-Host ""
    Write-Host "PORT OVERRIDES (one-time, do not persist to .env)" -ForegroundColor White
    Write-Host "  -FrontendPort PORT      Override frontend host port (default: 3000)"
    Write-Host "  -BackendPort PORT       Override backend host port (default: 8000)"
    Write-Host ""
    Write-Host "ENVIRONMENT VARIABLE OVERRIDES (persistent via .env)" -ForegroundColor White
    Write-Host "  EMBEDINATOR_PORT_FRONTEND     Frontend host port (default: 3000)"
    Write-Host "  EMBEDINATOR_PORT_BACKEND      Backend host port (default: 8000)"
    Write-Host "  EMBEDINATOR_PORT_QDRANT       Qdrant HTTP host port (default: 6333)"
    Write-Host "  EMBEDINATOR_PORT_QDRANT_GRPC  Qdrant gRPC host port (default: 6334)"
    Write-Host "  EMBEDINATOR_PORT_OLLAMA       Ollama host port (default: 11434)"
    Write-Host "  EMBEDINATOR_GPU               Force GPU profile: nvidia|amd|intel|none"
    Write-Host "  OLLAMA_MODELS                 Comma-separated models to download"
    Write-Host ""
    Write-Host "EXAMPLES" -ForegroundColor White
    Write-Host "  .\embedinator.ps1                      # First-time setup and start"
    Write-Host "  .\embedinator.ps1 -Open                # Start and open browser"
    Write-Host "  .\embedinator.ps1 -Dev                 # Start with hot reload"
    Write-Host "  .\embedinator.ps1 -Stop                # Stop all services"
    Write-Host "  .\embedinator.ps1 -Restart             # Restart all services"
    Write-Host "  .\embedinator.ps1 -Logs backend        # Stream backend logs"
    Write-Host "  .\embedinator.ps1 -Status              # Check service health"
    Write-Host "  .\embedinator.ps1 -FrontendPort 4000   # Use port 4000 for frontend"
    Write-Host "  .\embedinator.ps1 -BackendPort 9000    # Use port 9000 for backend"
    Write-Host ""
}

if ($Help) {
    Show-Help
    exit 0
}

# ── Load .env port overrides ──────────────────────────────────────────────────
function Load-EnvFile {
    if (-not (Test-Path '.env')) { return }
    $portKeys = @(
        'EMBEDINATOR_PORT_FRONTEND', 'EMBEDINATOR_PORT_BACKEND',
        'EMBEDINATOR_PORT_QDRANT',   'EMBEDINATOR_PORT_QDRANT_GRPC',
        'EMBEDINATOR_PORT_OLLAMA',   'OLLAMA_MODELS', 'EMBEDINATOR_GPU'
    )
    foreach ($line in Get-Content '.env') {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $kv = $line -split '=', 2
        $k = $kv[0].Trim()
        $v = $kv[1].Trim()
        if ($portKeys -contains $k -and -not [Environment]::GetEnvironmentVariable($k)) {
            [Environment]::SetEnvironmentVariable($k, $v, 'Process')
        }
    }
}

Load-EnvFile

# Apply env overrides
if ([Environment]::GetEnvironmentVariable('EMBEDINATOR_PORT_FRONTEND')) {
    $FRONTEND_PORT = [Environment]::GetEnvironmentVariable('EMBEDINATOR_PORT_FRONTEND')
}
if ([Environment]::GetEnvironmentVariable('EMBEDINATOR_PORT_BACKEND')) {
    $BACKEND_PORT = [Environment]::GetEnvironmentVariable('EMBEDINATOR_PORT_BACKEND')
}
if ([Environment]::GetEnvironmentVariable('EMBEDINATOR_PORT_QDRANT')) {
    $QDRANT_PORT = [Environment]::GetEnvironmentVariable('EMBEDINATOR_PORT_QDRANT')
}
if ([Environment]::GetEnvironmentVariable('EMBEDINATOR_PORT_QDRANT_GRPC')) {
    $QDRANT_GRPC = [Environment]::GetEnvironmentVariable('EMBEDINATOR_PORT_QDRANT_GRPC')
}
if ([Environment]::GetEnvironmentVariable('EMBEDINATOR_PORT_OLLAMA')) {
    $OLLAMA_PORT = [Environment]::GetEnvironmentVariable('EMBEDINATOR_PORT_OLLAMA')
}
if ([Environment]::GetEnvironmentVariable('OLLAMA_MODELS')) {
    $OLLAMA_MODELS = [Environment]::GetEnvironmentVariable('OLLAMA_MODELS')
}

# CLI port overrides (highest precedence)
if ($FrontendPort -ne '') {
    $FRONTEND_PORT = $FrontendPort
    [Environment]::SetEnvironmentVariable('EMBEDINATOR_PORT_FRONTEND', $FrontendPort, 'Process')
}
if ($BackendPort -ne '') {
    $BACKEND_PORT = $BackendPort
    [Environment]::SetEnvironmentVariable('EMBEDINATOR_PORT_BACKEND', $BackendPort, 'Process')
}

# Export all for Docker Compose interpolation
[Environment]::SetEnvironmentVariable('EMBEDINATOR_PORT_FRONTEND',  $FRONTEND_PORT, 'Process')
[Environment]::SetEnvironmentVariable('EMBEDINATOR_PORT_BACKEND',   $BACKEND_PORT,  'Process')
[Environment]::SetEnvironmentVariable('EMBEDINATOR_PORT_QDRANT',    $QDRANT_PORT,   'Process')
[Environment]::SetEnvironmentVariable('EMBEDINATOR_PORT_QDRANT_GRPC', $QDRANT_GRPC, 'Process')
[Environment]::SetEnvironmentVariable('EMBEDINATOR_PORT_OLLAMA',    $OLLAMA_PORT,   'Process')

# ── Compose args builder ──────────────────────────────────────────────────────
function Get-ComposeArgs {
    param([string]$GpuProfile, [bool]$DevMode)
    $args = @('-f', 'docker-compose.yml')
    switch ($GpuProfile) {
        'nvidia' { $args += @('-f', 'docker-compose.gpu-nvidia.yml') }
        'amd'    { $args += @('-f', 'docker-compose.gpu-amd.yml') }
        'intel'  { $args += @('-f', 'docker-compose.gpu-intel.yml') }
    }
    if ($DevMode) { $args += @('-f', 'docker-compose.dev.yml') }
    return $args
}

# ── GPU detection (Windows/WSL2) ──────────────────────────────────────────────
function Detect-Gpu {
    # Check env override first
    $gpuOverride = [Environment]::GetEnvironmentVariable('EMBEDINATOR_GPU')
    if ($gpuOverride) {
        if ($gpuOverride -in @('nvidia', 'amd', 'intel', 'none')) {
            Write-Info "GPU override: EMBEDINATOR_GPU=$gpuOverride"
            return $gpuOverride
        } else {
            Write-Warn "Invalid EMBEDINATOR_GPU='$gpuOverride'. Valid: nvidia|amd|intel|none. Falling back to auto-detect."
        }
    }

    # Windows: only NVIDIA supported via nvidia-smi in WSL2
    $nvidiaSmi = Get-Command 'nvidia-smi' -ErrorAction SilentlyContinue
    if ($nvidiaSmi) {
        try {
            $null = & nvidia-smi 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Info "NVIDIA GPU detected."
                return 'nvidia'
            }
        } catch { }
    }

    # AMD and Intel are not supported for GPU passthrough in Windows Docker Desktop
    # (WSL2 backend does not support /dev/kfd or /dev/dri passthrough)
    Write-Info "No supported GPU detected (or AMD/Intel not supported on Windows Docker). Using CPU mode."
    return 'none'
}

# ── Port conflict detection ───────────────────────────────────────────────────
function Test-PortAvailable {
    param([string]$Port, [string]$Name, [string]$Suggestion)
    try {
        $conn = Test-NetConnection -ComputerName localhost -Port ([int]$Port) -WarningAction SilentlyContinue -InformationLevel Quiet 2>$null
        if ($conn) {
            Write-Err "Port $Port ($Name) is already in use."
            Write-Err "  Resolution: .\embedinator.ps1 $Suggestion"
            return $false
        }
    } catch { }
    return $true
}

function Test-AllPorts {
    $failed = $false
    if (-not (Test-PortAvailable $FRONTEND_PORT "frontend" "-FrontendPort <PORT>")) { $failed = $true }
    if (-not (Test-PortAvailable $BACKEND_PORT  "backend"  "-BackendPort <PORT>"))  { $failed = $true }
    if (-not (Test-PortAvailable $QDRANT_PORT   "qdrant"   "(set EMBEDINATOR_PORT_QDRANT in .env)")) { $failed = $true }
    if (-not (Test-PortAvailable $OLLAMA_PORT   "ollama"   "(set EMBEDINATOR_PORT_OLLAMA in .env)")) { $failed = $true }
    if ($failed) { Die "Port conflicts detected. Resolve them and retry." }
}

# ── Preflight checks ──────────────────────────────────────────────────────────
function Invoke-PreflightChecks {
    Write-Info "Running preflight checks..."

    # 1. Docker daemon
    $dockerInfo = & docker info 2>$null
    if ($LASTEXITCODE -ne 0) {
        Die "Docker daemon is not running. Please start Docker Desktop and retry."
    }

    # 2. Docker Compose v2
    $null = & docker compose version 2>$null
    if ($LASTEXITCODE -ne 0) {
        Die "Docker Compose v2 is not available. Please upgrade Docker Desktop.`n  See: https://docs.docker.com/compose/install/"
    }

    # 3. Disk space warning (< 15GB)
    try {
        $drive = (Get-Location).Drive.Name + ':'
        $disk = Get-PSDrive -Name (Get-Location).Drive.Name -ErrorAction SilentlyContinue
        if ($disk -and $disk.Free) {
            $freeGB = [math]::Round($disk.Free / 1GB, 1)
            if ($freeGB -lt 15) {
                Write-Warn "Low disk space: ${freeGB}GB available. At least 15GB recommended."
            }
        }
    } catch { }

    # 4. WSL2 path warning (FR-055) — running ps1 from /mnt/c is unusual but check anyway
    if ($env:WSL_DISTRO_NAME -or $env:WSLENV) {
        Write-Warn "Running inside WSL2. For best performance, ensure the repo is on the WSL2 filesystem (not /mnt/c/...)."
    }

    Write-Success "Preflight checks passed."
}

# ── .env generation ───────────────────────────────────────────────────────────
$script:FirstRun = $false

function Invoke-EnvGeneration {
    if (Test-Path '.env') { return }

    if (-not (Test-Path '.env.example')) {
        Die ".env.example not found. Please run this script from the repository root."
    }

    Write-Info "First run: generating .env from .env.example..."
    Copy-Item '.env.example' '.env'

    Write-Info "Generating Fernet encryption key (using Docker - no local Python required)..."
    $fernetKey = ''
    try {
        $fernetKey = & docker run --rm python:3.14-slim python -c `
            "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>$null
        $fernetKey = $fernetKey.Trim()
    } catch {
        Die "Failed to generate Fernet key. Ensure Docker can pull 'python:3.14-slim' (check internet connection)."
    }

    if (-not $fernetKey) {
        Die "Fernet key generation returned empty output. Check Docker network connectivity."
    }

    # Inject into .env
    $envContent = Get-Content '.env'
    $updated = $envContent | ForEach-Object {
        if ($_ -match '^EMBEDINATOR_FERNET_KEY=') {
            "EMBEDINATOR_FERNET_KEY=$fernetKey"
        } else {
            $_
        }
    }
    if (-not ($envContent -match 'EMBEDINATOR_FERNET_KEY')) {
        $updated += "EMBEDINATOR_FERNET_KEY=$fernetKey"
    }
    $updated | Set-Content '.env'

    Write-Success "Generated .env with Fernet key."
    $script:FirstRun = $true
}

# ── CORS auto-detection ───────────────────────────────────────────────────────
function Update-CorsOrigins {
    $lanIp = ''
    try {
        $lanIp = (Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object { $_.InterfaceAlias -notmatch 'Loopback' -and $_.IPAddress -notmatch '^169\.' } |
            Select-Object -First 1).IPAddress
    } catch { }

    $corsValue = "http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}"
    if ($lanIp -and $lanIp -ne '127.0.0.1') {
        $corsValue += ",http://${lanIp}:${FRONTEND_PORT}"
    }

    $envContent = Get-Content '.env'
    $updated = $envContent | ForEach-Object {
        if ($_ -match '^CORS_ORIGINS=') { "CORS_ORIGINS=$corsValue" } else { $_ }
    }
    if (-not ($envContent -match 'CORS_ORIGINS')) {
        $updated += "CORS_ORIGINS=$corsValue"
    }
    $updated | Set-Content '.env'
}

# ── Data directories ──────────────────────────────────────────────────────────
function New-DataDirectories {
    New-Item -ItemType Directory -Force -Path 'data\uploads'  | Out-Null
    New-Item -ItemType Directory -Force -Path 'data\qdrant_db' | Out-Null
}

# ── Idempotency check ─────────────────────────────────────────────────────────
function Test-ServicesRunning {
    $output = & docker compose ps --quiet 2>$null
    return ($output -and $output.Trim().Length -gt 0)
}

# ── Health polling ─────────────────────────────────────────────────────────────
function Test-ServiceHealth {
    param([string]$Url)
    try {
        $null = Invoke-RestMethod -Uri $Url -TimeoutSec 3 -ErrorAction Stop 2>$null
        return $true
    } catch {
        return $false
    }
}

function Invoke-HealthPolling {
    param([int]$TimeoutSeconds)
    Write-Info "Waiting for services to be healthy (timeout: ${TimeoutSeconds}s)..."

    $start = Get-Date
    $qdrantOk  = $false
    $ollamaOk  = $false
    $backendOk = $false
    $frontendOk = $false

    while ($true) {
        $elapsed = [int]((Get-Date) - $start).TotalSeconds
        if ($elapsed -ge $TimeoutSeconds) {
            Write-Host ""
            Write-Err "Timeout waiting for services after ${TimeoutSeconds}s."
            Write-Err "Check logs: .\embedinator.ps1 -Logs"
            return $false
        }

        if (-not $qdrantOk)   { $qdrantOk   = Test-ServiceHealth "http://localhost:${QDRANT_PORT}/healthz" }
        if (-not $ollamaOk)   { $ollamaOk   = Test-ServiceHealth "http://localhost:${OLLAMA_PORT}/api/tags" }
        if (-not $backendOk)  { $backendOk  = Test-ServiceHealth "http://localhost:${BACKEND_PORT}/api/health/live" }
        if (-not $frontendOk) { $frontendOk = Test-ServiceHealth "http://localhost:${FRONTEND_PORT}/healthz" }

        $q = if ($qdrantOk)   { '[OK]' } else { '[..]' }
        $o = if ($ollamaOk)   { '[OK]' } else { '[..]' }
        $b = if ($backendOk)  { '[OK]' } else { '[..]' }
        $f = if ($frontendOk) { '[OK]' } else { '[..]' }

        Write-Host "`r  [$($elapsed)s] qdrant:$q ollama:$o backend:$b frontend:$f" -NoNewline

        if ($qdrantOk -and $ollamaOk -and $backendOk -and $frontendOk) {
            Write-Host ""
            Write-Success "All services are healthy."
            return $true
        }

        Start-Sleep -Seconds 3
    }
}

# ── Model pull ─────────────────────────────────────────────────────────────────
function Invoke-ModelPull {
    Write-Info "Checking AI models..."
    $existingModels = & docker compose exec ollama ollama list 2>$null
    $modelList = ($existingModels | Select-Object -Skip 1 | ForEach-Object { ($_ -split '\s+')[0] }) -join "`n"

    foreach ($model in ($OLLAMA_MODELS -split ',')) {
        $model = $model.Trim()
        if (-not $model) { continue }
        if ($modelList -match [regex]::Escape($model)) {
            Write-Success "Model already downloaded: $model"
        } else {
            Write-Info "Pulling model: $model (this may take several minutes on first run)..."
            try {
                & docker compose exec ollama ollama pull $model
            } catch {
                Write-Warn "Failed to pull model '$model'. You can retry: docker compose exec ollama ollama pull $model"
            }
        }
    }
}

# ── Status subcommand ─────────────────────────────────────────────────────────
function Show-Status {
    Write-Host ""
    Write-Host "Service Health Status" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor DarkGray

    function Show-ServiceStatus {
        param([string]$Name, [string]$Url, [string]$Port)
        $healthy = Test-ServiceHealth $Url
        $status = if ($healthy) { "healthy    " } else { "unreachable" }
        $color  = if ($healthy) { 'Green' } else { 'Red' }
        Write-Host ("  {0,-12} " -f $Name) -NoNewline
        Write-Host $status -ForegroundColor $color -NoNewline
        Write-Host "  port $Port"
    }

    Show-ServiceStatus "qdrant"   "http://localhost:${QDRANT_PORT}/healthz"           $QDRANT_PORT
    Show-ServiceStatus "ollama"   "http://localhost:${OLLAMA_PORT}/api/tags"           $OLLAMA_PORT
    Show-ServiceStatus "backend"  "http://localhost:${BACKEND_PORT}/api/health/live"  $BACKEND_PORT
    Show-ServiceStatus "frontend" "http://localhost:${FRONTEND_PORT}/healthz"          $FRONTEND_PORT
    Write-Host ""
}

# ── Browser open ──────────────────────────────────────────────────────────────
function Open-Browser {
    $url = "http://localhost:${FRONTEND_PORT}"
    Write-Info "Opening browser: $url"
    Start-Process $url
}

# ── Ready message ─────────────────────────────────────────────────────────────
function Print-Ready {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "  The Embedinator is ready!" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Application:  http://localhost:${FRONTEND_PORT}" -ForegroundColor White
    Write-Host "  Backend API:  http://localhost:${BACKEND_PORT}/api/health" -ForegroundColor White
    Write-Host ""
    Write-Host "  View logs:    .\embedinator.ps1 -Logs" -ForegroundColor DarkGray
    Write-Host "  Stop:         .\embedinator.ps1 -Stop" -ForegroundColor DarkGray
    Write-Host "  Status:       .\embedinator.ps1 -Status" -ForegroundColor DarkGray
    Write-Host ""
}

# ══════════════════════════════════════════════════════════════════════════════
# Subcommand dispatch
# ══════════════════════════════════════════════════════════════════════════════

$GpuProfile   = Detect-Gpu
$ComposeArgs  = Get-ComposeArgs -GpuProfile $GpuProfile -DevMode ($Dev.IsPresent)

# --stop
if ($Stop) {
    Write-Info "Stopping all services..."
    & docker compose @ComposeArgs down
    Write-Success "All services stopped."
    exit 0
}

# --restart
if ($Restart) {
    Write-Info "Restarting all services..."
    & docker compose @ComposeArgs down
    Write-Success "Services stopped. Starting again..."
    # Fall through to start flow
}

# --logs
if ($Logs) {
    if ($LogsService) {
        & docker compose @ComposeArgs logs -f $LogsService
    } else {
        & docker compose @ComposeArgs logs -f
    }
    exit 0
}

# --status
if ($Status) {
    Show-Status
    exit 0
}

# ── Start flow ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "The Embedinator - Starting up" -ForegroundColor White
Write-Host ""

Invoke-PreflightChecks

Write-Info "GPU profile: $GpuProfile"

Test-AllPorts

Invoke-EnvGeneration
Update-CorsOrigins
New-DataDirectories

# Idempotency check
if (Test-ServicesRunning) {
    Write-Warn "Services are already running. Reporting status instead of starting duplicate containers."
    Show-Status
    exit 0
}

# Health timeout: 300s first run, 60s subsequent
$healthTimeout = if ($script:FirstRun) { 300 } else { 60 }
if ($script:FirstRun) {
    Write-Info "First run detected - using extended timeout (${healthTimeout}s) for image builds and model downloads."
}

if ($Dev) {
    Write-Info "Starting in developer mode (hot reload)..."
} else {
    Write-Info "Starting services..."
}

& docker compose @ComposeArgs up --build -d

$healthy = Invoke-HealthPolling -TimeoutSeconds $healthTimeout
if (-not $healthy) { exit 1 }

Invoke-ModelPull

if ($Open) { Open-Browser }

Print-Ready
