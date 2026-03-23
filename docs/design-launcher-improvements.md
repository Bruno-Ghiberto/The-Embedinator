# Design: Launcher Script Improvements

**Date**: 2026-03-23
**Status**: Proposed
**Scope**: `embedinator.sh`, `embedinator.ps1`, `docker-compose.yml`
**Constraint**: Makefile is SACRED -- zero changes.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Design Principles](#2-design-principles)
3. [Feature 1: Ollama Desktop Detection](#3-feature-1-ollama-desktop-detection)
4. [Feature 2: Interactive Port Conflict Resolution](#4-feature-2-interactive-port-conflict-resolution)
5. [Docker Compose Changes](#5-docker-compose-changes)
6. [CLI Surface Changes](#6-cli-surface-changes)
7. [Edge Cases and Failure Modes](#7-edge-cases-and-failure-modes)
8. [PowerShell Parity](#8-powershell-parity)
9. [File Change Summary](#9-file-change-summary)
10. [Rejected Alternatives](#10-rejected-alternatives)

---

## 1. Problem Statement

### 1.1 Ollama Desktop Conflict

Users who have Ollama Desktop installed locally face a subtle and confusing failure mode:

- Ollama Desktop binds to `0.0.0.0:11434` by default -- the same port Docker Ollama uses.
- The launcher's port conflict check (`check_port`) catches this and exits with an error, but the error message says "Port 11434 (ollama) is already in use" with no specific guidance.
- Worse, if the user has _already_ set `EMBEDINATOR_PORT_OLLAMA` to a different host port (e.g., 11435), the Docker Ollama container starts on 11435 while the backend container still talks to `ollama:11434` via Docker networking. This works correctly. But the **launcher's health check** (`poll_all_services`) polls `localhost:${OLLAMA_PORT}` -- which on 11435 hits the Docker Ollama, while `localhost:11434` still answers from Ollama Desktop. The user may not realize which Ollama is which.
- If the user accidentally configures the **backend** to use local Ollama (by overriding `OLLAMA_BASE_URL` to `http://host.docker.internal:11434`), models pulled into Docker Ollama's volume won't be available, and vice versa.

The core question: **should the launcher reuse local Ollama or always use Docker Ollama?**

### 1.2 Port Conflicts

All five host ports (3000, 8000, 6333, 6334, 11434) are commonly used. The current behavior is to detect conflicts and exit with an error message suggesting manual CLI flags or env vars. This is correct but hostile to new users who just want to get started.

---

## 2. Design Principles

1. **Non-interactive by default.** CI/CD, scripted invocations, and piped stdin must never hang on a prompt. Interactive prompts only fire when `stdin` is a terminal AND a conflict is detected.
2. **Explicit over implicit.** The launcher must never silently pick a different Ollama or port. Every deviation from defaults is printed clearly.
3. **Docker-first.** Docker Ollama is the canonical inference service. Reusing local Ollama is an opt-in escape hatch, not the default path.
4. **Idempotent.** Running the launcher twice with the same inputs produces the same result.
5. **No Makefile changes.** The Makefile is SACRED.

---

## 3. Feature 1: Ollama Desktop Detection

### 3.1 Decision: Docker Ollama is Always the Default

**Rationale:**

| Factor | Docker Ollama | Local Ollama |
|--------|--------------|--------------|
| Model isolation | Models are in a Docker volume, managed by the launcher's `pull_models` step. | Models live in `~/.ollama/models`. Different set, different versions. |
| Network path | Backend reaches Ollama via `ollama:11434` (Docker DNS). Predictable, zero-config. | Backend would need `host.docker.internal:11434` or the host's LAN IP. Cross-platform headaches (host.docker.internal is unreliable on Linux). |
| GPU passthrough | Controlled by GPU overlay files. Tested. | User's local Ollama already has GPU access natively. No Docker overhead. |
| Reproducibility | Same container image, same behavior across machines. | Version drift, different quantizations, user-modified Modelfiles. |
| macOS performance | Docker Desktop on macOS cannot pass GPU. CPU-only, slow. | Native Ollama on macOS uses Metal GPU. Significantly faster. |

**Conclusion:** Docker Ollama is the default because it guarantees reproducibility and eliminates "works on my machine" issues. However, on **macOS**, using local Ollama is strongly preferred because Docker Desktop cannot pass through the Metal GPU -- this is the single case where local Ollama is materially better.

The launcher will support an **opt-in flag** to skip Docker Ollama and connect to a local Ollama instance instead.

### 3.2 Detection Logic

A new function `detect_local_ollama()` runs during preflight, before port checks:

```
detect_local_ollama():
  1. Check if an Ollama process is running:
     - Linux/macOS: `pgrep -x ollama` OR `pidof ollama`
     - Windows (PS): `Get-Process ollama -ErrorAction SilentlyContinue`
  2. If process found, probe the API:
     - GET http://localhost:11434/api/tags (timeout: 2s)
     - If 200: local Ollama is alive. Extract version from response headers
       (`x-ollama-version`) and model list.
  3. Return: { running: bool, api_reachable: bool, version: string, models: string[] }
```

### 3.3 Behavior Matrix

| Scenario | `--use-local-ollama` flag | Action |
|----------|--------------------------|--------|
| No local Ollama detected | Not set | Normal startup. Docker Ollama on default port. |
| No local Ollama detected | Set | Error: "Local Ollama not found. Remove --use-local-ollama or start Ollama Desktop." |
| Local Ollama detected, port 11434 | Not set | Warn user. Offer interactive prompt if TTY. Non-TTY: error with remediation instructions. |
| Local Ollama detected, port 11434 | Set | Skip Docker Ollama service. Connect backend to local Ollama. |
| Local Ollama detected, macOS | Not set | Stronger recommendation to use local (Metal GPU advantage). Still requires explicit opt-in. |
| `EMBEDINATOR_USE_LOCAL_OLLAMA=1` in env/.env | N/A | Same as `--use-local-ollama`. Env var is the persistent equivalent. |

### 3.4 Interactive Prompt (TTY only)

When local Ollama is detected and `--use-local-ollama` is NOT set, and `stdin` is a terminal:

```
[embedinator] WARNING: Ollama Desktop is running on port 11434.

  The Embedinator uses its own Ollama instance inside Docker by default.
  Having both will cause a port conflict on 11434.

  Options:
    [1] Use local Ollama (skip Docker Ollama, connect backend to your local instance)
    [2] Use Docker Ollama on a different port (auto-assign 11435)
    [3] Abort (I'll handle it myself)

  Recommendation: On macOS, option [1] gives you Metal GPU acceleration.
                  On Linux with NVIDIA GPU, option [2] keeps Docker GPU passthrough.

  Choose [1/2/3] (default: 2):
```

- **Option 1**: Sets `EMBEDINATOR_USE_LOCAL_OLLAMA=1` for this run. Removes `ollama` from Docker Compose profiles (see section 5). Sets `OLLAMA_BASE_URL` for the backend.
- **Option 2**: Sets `EMBEDINATOR_PORT_OLLAMA=11435` (or next available) and proceeds normally.
- **Option 3**: Exits with code 1.

When stdin is NOT a terminal (piped, CI):

```
[embedinator] ERROR: Port 11434 (ollama) is already in use (PID 12345: ollama).
[embedinator] ERROR:   Local Ollama Desktop is running. Choose one:
[embedinator] ERROR:     a) Use local Ollama:  EMBEDINATOR_USE_LOCAL_OLLAMA=1 ./embedinator.sh
[embedinator] ERROR:     b) Move Docker Ollama: EMBEDINATOR_PORT_OLLAMA=11435 ./embedinator.sh
[embedinator] ERROR:     c) Stop local Ollama:  killall ollama (or quit Ollama Desktop)
```

### 3.5 "Use Local Ollama" Mode -- What Changes

When `EMBEDINATOR_USE_LOCAL_OLLAMA=1` (or `--use-local-ollama`):

1. **Docker Compose**: The `ollama` service is excluded. This is done by passing `--scale ollama=0` to `docker compose up`, which skips the service without modifying the YAML.
2. **Backend environment**: `OLLAMA_BASE_URL` must point to local Ollama. On Linux, the backend container reaches the host via `host.docker.internal` (requires Docker 20.10+) or the host's gateway IP. On macOS, `host.docker.internal` is reliable.
   - The launcher sets `OLLAMA_BASE_URL=http://host.docker.internal:11434` in the environment passed to `docker compose`.
3. **Backend `depends_on`**: The backend currently has `depends_on: ollama: condition: service_healthy`. When `ollama` is scaled to 0, this dependency is skipped by Compose automatically (the service doesn't exist in the effective config).
   - **Correction**: `--scale ollama=0` does NOT remove the `depends_on` constraint. Docker Compose will error. Instead, we need a **Compose profile**.
4. **Model pull**: `pull_models()` changes behavior:
   - Instead of `docker compose exec ollama ollama pull $model`, it runs `ollama pull $model` directly on the host (assumes `ollama` CLI is in PATH).
   - If `ollama` CLI is not found, warn and skip (user's local Ollama already has its own models).
5. **Health check**: `poll_all_services()` polls `localhost:11434` for Ollama (same as now, since local Ollama is on the host).

### 3.6 Docker Compose Profile Approach

The `depends_on` problem (section 3.5 point 3) rules out `--scale ollama=0`. The correct Docker Compose mechanism is **profiles**.

Changes to `docker-compose.yml`:

```yaml
services:
  ollama:
    profiles: ["docker-ollama"]   # <-- NEW: only starts when profile is active
    image: ollama/ollama:latest
    # ... rest unchanged

  backend:
    depends_on:
      qdrant:
        condition: service_healthy
      ollama:                        # This is REMOVED when not using docker-ollama profile
        condition: service_healthy
```

Wait -- this creates a problem. If `ollama` is in a profile and not activated, but `backend` still has `depends_on: ollama`, Compose errors out. The `depends_on` must be conditional.

**Revised approach: two backend definitions via overlay.**

Rather than modifying `docker-compose.yml` (which would add complexity to the default path), use a **new overlay file** `docker-compose.local-ollama.yml`:

```yaml
# docker-compose.local-ollama.yml
# Overlay: disables Docker Ollama and connects backend to host Ollama
services:
  ollama:
    deploy:
      replicas: 0          # Effectively disables the service
    entrypoint: ["true"]    # No-op entrypoint (in case Compose still spins it up briefly)
    healthcheck:
      test: ["CMD", "true"]
      interval: 1s
      retries: 1

  backend:
    depends_on:
      qdrant:
        condition: service_healthy
      # ollama dependency removed by re-declaring depends_on without it
    environment:
      OLLAMA_BASE_URL: http://host.docker.internal:11434
    extra_hosts:
      - "host.docker.internal:host-gateway"   # Required on Linux (Docker 20.10+)
```

**Problem**: Docker Compose merges `depends_on` maps -- it does not replace. So declaring `depends_on` with only `qdrant` in the overlay will ADD qdrant but NOT remove ollama.

**Final approach: use Compose profiles correctly.**

```yaml
# In docker-compose.yml (modified):
services:
  ollama:
    profiles: ["with-docker-ollama"]
    # ... rest unchanged

  backend:
    # depends_on for ollama is REMOVED from the base file.
    # It is added back via the docker-ollama overlay.
    depends_on:
      qdrant:
        condition: service_healthy
```

Then a new overlay `docker-compose.docker-ollama.yml`:

```yaml
# docker-compose.docker-ollama.yml
# Adds Docker Ollama dependency to backend (default path)
services:
  ollama:
    profiles: []   # Override: always start (empty profiles = no profile gating)

  backend:
    depends_on:
      qdrant:
        condition: service_healthy
      ollama:
        condition: service_healthy
```

This is getting too complex. Profiles in Compose are meant for exactly this, but the `depends_on` interaction makes them awkward.

**SELECTED APPROACH: Simplest correct solution.**

Keep `docker-compose.yml` unchanged. Introduce ONE new overlay file:

```yaml
# docker-compose.local-ollama.yml
services:
  # Override ollama to be a no-op
  ollama:
    image: busybox:latest
    entrypoint: ["sh", "-c", "echo 'Ollama disabled (using local)' && sleep infinity"]
    healthcheck:
      test: ["CMD", "true"]
      interval: 2s
      timeout: 1s
      retries: 1
      start_period: 0s
    deploy: {}          # Clear GPU reservations from base
    volumes: []         # Don't mount ollama_models
    ports: []           # Don't bind any ports

  backend:
    environment:
      OLLAMA_BASE_URL: http://host.docker.internal:11434
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

This approach:
- Replaces the `ollama` service with a minimal busybox that does nothing but satisfy `depends_on`.
- The busybox container's healthcheck immediately returns true, so `backend` starts without waiting.
- Overrides `OLLAMA_BASE_URL` to point the backend at the host's Ollama.
- Adds `host.docker.internal` mapping for Linux compatibility.
- No changes to `docker-compose.yml` itself.
- The overlay is only included when `--use-local-ollama` is active.

The launcher's `build_compose_args()` adds `-f docker-compose.local-ollama.yml` when local Ollama mode is active.

### 3.7 Model Pull in Local Ollama Mode

When local Ollama mode is active, the `pull_models()` function changes:

```
pull_models():
  if USE_LOCAL_OLLAMA:
    # Check if ollama CLI is available on the host
    if ! command -v ollama:
      warn "Ollama CLI not found in PATH. Skipping model pull."
      warn "Ensure your local Ollama has the required models: $OLLAMA_MODELS"
      return

    existing = ollama list  # direct host command
    for model in OLLAMA_MODELS:
      if model in existing:
        success "Model already available locally: $model"
      else:
        info "Pulling model via local Ollama: $model"
        ollama pull $model
  else:
    # existing Docker-based logic unchanged
```

### 3.8 Health Check Adjustments

`poll_all_services()` for the Ollama slot:
- **Docker Ollama mode (default)**: Poll `localhost:${OLLAMA_PORT}/api/tags` -- unchanged.
- **Local Ollama mode**: Poll `localhost:11434/api/tags` (always 11434, the local Ollama's actual port). The `EMBEDINATOR_PORT_OLLAMA` variable is irrelevant in this mode since no Docker port mapping exists.

---

## 4. Feature 2: Interactive Port Conflict Resolution

### 4.1 Overview

Replace the current "error and die" behavior in `check_all_ports()` with a three-tier response:

1. **Non-interactive** (stdin is not a TTY): Print error with specific remediation commands. Exit 1. (Same as today but with better messaging.)
2. **Interactive with auto-resolution available**: Detect the conflict, propose an alternative port, and ask the user to confirm.
3. **Persistent override**: Optionally write the chosen port to `.env` so subsequent runs don't ask again.

### 4.2 Port Availability Scanner

A new helper function finds the next available port starting from a base:

```
find_available_port(start_port, max_attempts=10):
  for port in range(start_port, start_port + max_attempts):
    if port is available:
      return port
  return null  # all 10 candidates are taken
```

Port availability check:
- **Bash**: `! lsof -i :${port} &>/dev/null 2>&1` (existing pattern) OR `! ss -tlnp | grep -q ":${port} "` as fallback.
- **PowerShell**: `Test-NetConnection` (existing pattern).

### 4.3 Interactive Flow

When a port conflict is detected and stdin is a TTY:

```
[embedinator] WARNING: Port 3000 (frontend) is already in use (PID 8421: node).

  [1] Use alternative port 3001 (auto-detected as available)
  [2] Enter a custom port
  [3] Abort

  Choose [1/2/3] (default: 1):
```

**Option 1**: Use the auto-suggested port. Export it for this Docker Compose session.
**Option 2**: Read custom port from stdin. Validate it (numeric, 1024-65535, not already in use). Retry if invalid.
**Option 3**: Exit 1.

After resolution (option 1 or 2):

```
  Save this port to .env for future runs? [y/N]:
```

If yes: append/update `EMBEDINATOR_PORT_FRONTEND=3001` in `.env`.

### 4.4 Non-Interactive Flow

When stdin is NOT a TTY:

```
[embedinator] ERROR: Port 3000 (frontend) is already in use (PID 8421: node).
[embedinator] ERROR:   Fix: ./embedinator.sh --frontend-port 3001
[embedinator] ERROR:   Or:  export EMBEDINATOR_PORT_FRONTEND=3001
```

The error message now includes a **concrete suggested port** (the next available one), rather than a generic "use --frontend-port <PORT>".

Exit 1.

### 4.5 Multiple Conflicts

If more than one port is in conflict, all conflicts are detected first (as today), then interactive prompts are shown sequentially:

```
[embedinator] WARNING: 2 port conflicts detected.

  Port 3000 (frontend) is in use (PID 8421: node).
    [1] Use 3001  [2] Custom  [3] Abort
    Choose [1/2/3] (default: 1): 1
    --> Frontend will use port 3001

  Port 11434 (ollama) is in use (PID 12345: ollama).
    [1] Use 11435  [2] Custom  [3] Abort
    Choose [1/2/3] (default: 1): 1
    --> Ollama will use port 11435

  Save these ports to .env? [y/N]: y
  --> Updated .env: EMBEDINATOR_PORT_FRONTEND=3001, EMBEDINATOR_PORT_OLLAMA=11435
```

### 4.6 Interaction with Ollama Detection

If the process on port 11434 is identified as Ollama, the port conflict prompt is **replaced** by the Ollama-specific prompt from section 3.4. The generic port prompt is NOT shown for the Ollama port when local Ollama is detected -- the Ollama-specific prompt handles it with better options (use local, relocate Docker, abort).

Detection order in `check_all_ports()`:

```
1. For each port:
   a. Check if port is in use
   b. If in use, identify process name
   c. If port == OLLAMA_PORT and process is "ollama":
      -> Set flag: OLLAMA_CONFLICT=local_ollama
      -> Do NOT add to generic conflict list
   d. Else:
      -> Add to generic conflict list

2. If OLLAMA_CONFLICT == local_ollama:
   -> Run Ollama-specific prompt (section 3.4)
   -> Result may set USE_LOCAL_OLLAMA or change OLLAMA_PORT

3. For remaining generic conflicts:
   -> Run generic port prompt (section 4.3) for each
```

### 4.7 CORS Auto-Update

When a port is changed (either interactively or via CLI flag), the `update_cors()` function already uses `$FRONTEND_PORT` which will reflect the override. No additional changes needed.

### 4.8 Port Validation Rules

- Must be numeric.
- Must be in range 1024-65535 (no privileged ports).
- Must not be currently in use.
- Must not conflict with another Embedinator service port (e.g., user picks 8000 for frontend while backend is already assigned 8000).

---

## 5. Docker Compose Changes

### 5.1 New File: `docker-compose.local-ollama.yml`

As described in section 3.6. This is the ONLY new Compose file. `docker-compose.yml` itself is **unchanged**.

### 5.2 `build_compose_args()` Update

```bash
build_compose_args() {
  local gpu_profile="$1"
  local dev_mode="$2"
  local use_local_ollama="$3"    # NEW parameter
  local args="-f docker-compose.yml"

  # Local ollama overlay (must come before GPU overlays)
  if [[ "$use_local_ollama" == "true" ]]; then
    args="$args -f docker-compose.local-ollama.yml"
    # GPU overlay is irrelevant when not using Docker Ollama
  else
    case "$gpu_profile" in
      nvidia) args="$args -f docker-compose.gpu-nvidia.yml" ;;
      amd)    args="$args -f docker-compose.gpu-amd.yml" ;;
      intel)  args="$args -f docker-compose.gpu-intel.yml" ;;
    esac
  fi

  if [[ "$dev_mode" == "true" ]]; then
    args="$args -f docker-compose.dev.yml"
  fi

  echo "$args"
}
```

Note: GPU overlays are skipped in local Ollama mode because the Docker Ollama container is a no-op busybox -- there is no point configuring GPU passthrough for it.

---

## 6. CLI Surface Changes

### 6.1 New Flag: `--use-local-ollama`

```
--use-local-ollama        Skip Docker Ollama; connect backend to locally-running Ollama
```

**Equivalent env var**: `EMBEDINATOR_USE_LOCAL_OLLAMA=1`

### 6.2 New Flag: `--no-interactive`

```
--no-interactive          Never prompt for input (same as non-TTY behavior)
```

This gives users explicit control in edge cases where stdin is technically a TTY but they don't want prompts (e.g., running from an IDE terminal via a macro).

### 6.3 Updated Help Text

The help text gains two new entries in the OPTIONS section and a new section:

```
OLLAMA MODE
  --use-local-ollama      Skip Docker Ollama; connect to locally-installed Ollama
                          (env: EMBEDINATOR_USE_LOCAL_OLLAMA=1)

BEHAVIOR
  --no-interactive        Suppress interactive prompts (auto-fail on conflicts)
```

### 6.4 No New Makefile Targets

The Makefile is SACRED. These features are launcher-script-only.

---

## 7. Edge Cases and Failure Modes

### 7.1 Ollama Desktop Starts After Launcher

User starts The Embedinator (Docker Ollama on 11434), then later launches Ollama Desktop. Ollama Desktop will fail to bind 11434 (port taken by Docker). This is fine -- Docker Ollama wins. No action needed from the launcher.

### 7.2 Local Ollama Without Required Models

User opts into `--use-local-ollama` but their local Ollama doesn't have `qwen2.5:7b` or `nomic-embed-text`. The `pull_models()` function handles this -- it will attempt `ollama pull` on the host. If the `ollama` CLI isn't in PATH, warn and continue. The backend's health check will report model-not-found, giving the user a clear signal.

### 7.3 `host.docker.internal` Fails on Older Docker (Linux)

On Linux, `host.docker.internal` requires Docker Engine 20.10+ with `extra_hosts: host.docker.internal:host-gateway`. The overlay includes this. If Docker is older:
- The launcher checks Docker version during preflight.
- If < 20.10 and `--use-local-ollama` is set on Linux, error with: "Local Ollama mode requires Docker Engine 20.10+. Current version: X.Y."

### 7.4 Port Conflict with Stopped Container

`lsof` / `ss` detect TCP listeners. A stopped Docker container doesn't hold ports. However, if a container is in "restarting" state, it may hold the port intermittently. The idempotency check (`check_already_running`) runs before port checks and returns early if Embedinator services are already running. This handles the case.

### 7.5 User Has Custom `OLLAMA_BASE_URL` in `.env`

If `.env` contains `OLLAMA_BASE_URL=http://some-remote-server:11434`, the user is already managing Ollama externally. The launcher should NOT override this with `host.docker.internal`. Detection:
- If `OLLAMA_BASE_URL` is set in `.env` to something other than the default (`http://ollama:11434`), the local-ollama overlay does NOT set `OLLAMA_BASE_URL`. The user's explicit override takes precedence.
- A warning is printed: "Custom OLLAMA_BASE_URL detected in .env. Local Ollama mode will use your configured URL."

### 7.6 WSL2 Networking

On WSL2, `host.docker.internal` behavior depends on the Docker Desktop networking mode. In the default "WSL2 backend" mode, it resolves correctly. In the older "Hyper-V" mode, it may not. The PowerShell launcher can detect this via `docker context inspect` and warn if the backend is not WSL2.

### 7.7 Race Condition: Port Freed Between Check and Docker Start

The launcher checks ports, then runs `docker compose up`. If another process grabs the port in between, Docker Compose will error with "bind: address already in use". This is an inherent TOCTOU race. Mitigation: none needed -- Docker's error message is clear enough, and this is an extremely rare window (sub-second).

### 7.8 User Answers Prompt Then Ctrl+C

If the user answers the interactive prompt (e.g., picks option 1) then Ctrl+C before Docker Compose starts, the `.env` may have been updated but services aren't running. This is fine -- the next `./embedinator.sh` invocation will use the saved port from `.env`.

---

## 8. PowerShell Parity

Both features must be implemented in `embedinator.ps1` with identical behavior. Key differences in implementation:

### 8.1 Ollama Detection

```powershell
function Detect-LocalOllama {
    $proc = Get-Process -Name 'ollama' -ErrorAction SilentlyContinue
    if (-not $proc) { return @{ Running = $false } }

    try {
        $resp = Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -TimeoutSec 2
        $models = ($resp.models | ForEach-Object { $_.name })
        return @{ Running = $true; ApiReachable = $true; Models = $models }
    } catch {
        return @{ Running = $true; ApiReachable = $false; Models = @() }
    }
}
```

### 8.2 TTY Detection

```powershell
# PowerShell: [Environment]::UserInteractive AND -not $env:CI
$IsInteractive = [Environment]::UserInteractive -and -not $env:CI -and -not $NoInteractive
```

Bash equivalent:
```bash
is_interactive() {
  [[ -t 0 ]] && [[ -z "${CI:-}" ]] && [[ "$NO_INTERACTIVE" != "true" ]]
}
```

### 8.3 New Parameters

```powershell
[switch]$UseLocalOllama,
[switch]$NoInteractive
```

### 8.4 Port Scanner

```powershell
function Find-AvailablePort {
    param([int]$StartPort, [int]$MaxAttempts = 10)
    for ($p = $StartPort; $p -lt $StartPort + $MaxAttempts; $p++) {
        $inUse = Test-NetConnection -ComputerName localhost -Port $p -WarningAction SilentlyContinue -InformationLevel Quiet 2>$null
        if (-not $inUse) { return $p }
    }
    return $null
}
```

### 8.5 GPU Overlay Note

On Windows, only NVIDIA GPU passthrough is supported. The `--use-local-ollama` flag is particularly relevant on Windows because AMD/Intel GPUs cannot be passed through to Docker -- local Ollama with DirectML gives better performance for those users.

---

## 9. File Change Summary

| File | Change Type | Description |
|------|------------|-------------|
| `embedinator.sh` | Modified | Add `detect_local_ollama()`, refactor `check_all_ports()` to `resolve_port_conflicts()`, update `build_compose_args()`, `pull_models()`, `poll_all_services()`. New flags: `--use-local-ollama`, `--no-interactive`. |
| `embedinator.ps1` | Modified | Equivalent changes to bash script. New params: `-UseLocalOllama`, `-NoInteractive`. |
| `docker-compose.local-ollama.yml` | **New file** | Overlay that replaces Docker Ollama with busybox no-op and points backend at host Ollama. |
| `docker-compose.yml` | **Unchanged** | No modifications needed. |
| `docker-compose.gpu-*.yml` | **Unchanged** | No modifications needed. |
| `Makefile` | **Unchanged** | SACRED. |
| `backend/*` | **Unchanged** | Backend already reads `OLLAMA_BASE_URL` from environment. No code changes needed. |
| `.env.example` | Modified | Add `EMBEDINATOR_USE_LOCAL_OLLAMA=` (commented out, with documentation) |

### 9.1 Estimated Line Changes

- `embedinator.sh`: +120 lines (new functions), ~30 lines modified (existing functions)
- `embedinator.ps1`: +100 lines (new functions), ~25 lines modified (existing functions)
- `docker-compose.local-ollama.yml`: ~20 lines (new file)
- `.env.example`: +3 lines (new commented variable)

---

## 10. Rejected Alternatives

### 10.1 Auto-Detect and Silently Reuse Local Ollama

Rejected because it violates "explicit over implicit." A user who installed Ollama Desktop for personal projects should not have The Embedinator silently connect to it. Model versions, quantizations, and configurations may differ. Silent reuse would create "works on my machine" debugging nightmares.

### 10.2 Auto-Assign Ports Without Prompting

Rejected for the same reason. Silently moving the frontend to port 3001 means the user's bookmarks, browser tabs, and muscle memory all break. The user must explicitly acknowledge the change.

### 10.3 Kill Local Ollama Automatically

Rejected. The launcher should never terminate user processes. It can _suggest_ `killall ollama` but must not execute it.

### 10.4 Modify `docker-compose.yml` with `profiles`

Rejected due to the `depends_on` interaction complexity described in section 3.6. The overlay approach keeps `docker-compose.yml` unchanged and avoids breaking existing workflows.

### 10.5 Use `--scale ollama=0`

Rejected because Docker Compose does not skip `depends_on` for scaled-to-zero services. The backend would fail to start.

### 10.6 Separate `docker-compose.no-ollama.yml` That Omits Ollama Entirely

Rejected because maintaining a second full Compose file creates drift risk. The overlay approach (section 3.6) replaces only what's needed.
