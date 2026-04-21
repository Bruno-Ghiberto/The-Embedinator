#!/usr/bin/env bash
# embedinator.sh — Single-command launcher for The Embedinator
# Usage: ./embedinator.sh [--dev] [--stop] [--restart] [--logs [service]]
#        [--status] [--open] [--help] [--frontend-port PORT] [--backend-port PORT]
set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

FRONTEND_PORT="${EMBEDINATOR_PORT_FRONTEND:-3000}"
BACKEND_PORT="${EMBEDINATOR_PORT_BACKEND:-8000}"
QDRANT_PORT="${EMBEDINATOR_PORT_QDRANT:-6333}"
QDRANT_GRPC_PORT="${EMBEDINATOR_PORT_QDRANT_GRPC:-6334}"
OLLAMA_PORT="${EMBEDINATOR_PORT_OLLAMA:-11434}"
OLLAMA_MODELS="${OLLAMA_MODELS:-qwen2.5:7b,nomic-embed-text}"

CMD_DEV=false
CMD_STOP=false
CMD_RESTART=false
CMD_LOGS=false
CMD_STATUS=false
CMD_OPEN=false
CMD_HELP=false
LOGS_SERVICE=""
CLI_FRONTEND_PORT=""
CLI_BACKEND_PORT=""

# ── Color helpers ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[embedinator]${NC} $*"; }
success() { echo -e "${GREEN}[embedinator]${NC} $*"; }
warn()    { echo -e "${YELLOW}[embedinator] WARNING:${NC} $*"; }
error()   { echo -e "${RED}[embedinator] ERROR:${NC} $*" >&2; }
die()     { error "$*"; exit 1; }

# ── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev)            CMD_DEV=true;  shift ;;
    --stop)           CMD_STOP=true; shift ;;
    --restart)        CMD_RESTART=true; shift ;;
    --logs)
      CMD_LOGS=true
      if [[ $# -gt 1 && "$2" != --* ]]; then
        LOGS_SERVICE="$2"; shift
      fi
      shift ;;
    --status)         CMD_STATUS=true; shift ;;
    --open)           CMD_OPEN=true; shift ;;
    --help|-h)        CMD_HELP=true; shift ;;
    --frontend-port)
      [[ $# -gt 1 ]] || die "--frontend-port requires a PORT argument"
      CLI_FRONTEND_PORT="$2"; shift 2 ;;
    --backend-port)
      [[ $# -gt 1 ]] || die "--backend-port requires a PORT argument"
      CLI_BACKEND_PORT="$2"; shift 2 ;;
    *)
      die "Unknown option: $1. Run ./embedinator.sh --help for usage." ;;
  esac
done

# ── Help ─────────────────────────────────────────────────────────────────────
show_help() {
  echo -e "${BOLD}The Embedinator — Launcher Script${NC}"
  echo ""
  echo -e "${BOLD}USAGE${NC}"
  echo "  ./embedinator.sh [OPTIONS]"
  echo ""
  echo -e "${BOLD}SUBCOMMANDS${NC}"
  echo "  (no flags)              Start all services (first-run or resume)"
  echo "  --dev                   Start with dev overlay (hot reload)"
  echo "  --stop                  Stop all running services"
  echo "  --restart               Stop then start all services"
  echo "  --logs [SERVICE]        Stream logs (all services or one: qdrant|ollama|backend|frontend)"
  echo "  --status                Show health status of all services"
  echo "  --open                  Open the application in the default browser after startup"
  echo "  --help                  Show this help message"
  echo ""
  echo -e "${BOLD}PORT OVERRIDES (one-time, do not persist to .env)${NC}"
  echo "  --frontend-port PORT    Override frontend host port (default: 3000)"
  echo "  --backend-port PORT     Override backend host port (default: 8000)"
  echo ""
  echo -e "${BOLD}ENVIRONMENT VARIABLE OVERRIDES (persistent via .env)${NC}"
  echo "  EMBEDINATOR_PORT_FRONTEND   Frontend host port (default: 3000)"
  echo "  EMBEDINATOR_PORT_BACKEND    Backend host port (default: 8000)"
  echo "  EMBEDINATOR_PORT_QDRANT     Qdrant HTTP host port (default: 6333)"
  echo "  EMBEDINATOR_PORT_QDRANT_GRPC Qdrant gRPC host port (default: 6334)"
  echo "  EMBEDINATOR_PORT_OLLAMA     Ollama host port (default: 11434)"
  echo "  EMBEDINATOR_GPU             Force GPU profile: nvidia|amd|intel|none"
  echo "  OLLAMA_MODELS               Comma-separated models to download (default: qwen2.5:7b,nomic-embed-text)"
  echo ""
  echo -e "${BOLD}EXAMPLES${NC}"
  echo "  ./embedinator.sh                          # First-time setup and start"
  echo "  ./embedinator.sh --open                   # Start and open browser"
  echo "  ./embedinator.sh --dev                    # Start with hot reload"
  echo "  ./embedinator.sh --stop                   # Stop all services"
  echo "  ./embedinator.sh --restart                # Restart all services"
  echo "  ./embedinator.sh --logs backend           # Stream backend logs"
  echo "  ./embedinator.sh --status                 # Check service health"
  echo "  ./embedinator.sh --frontend-port 4000     # Use port 4000 for frontend"
  echo "  ./embedinator.sh --backend-port 9000      # Use port 9000 for backend"
}

if $CMD_HELP; then
  show_help
  exit 0
fi

# ── Detect OS ─────────────────────────────────────────────────────────────────
detect_os() {
  case "$(uname -s)" in
    Darwin) echo "macos" ;;
    Linux)
      if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "wsl2"
      else
        echo "linux"
      fi
      ;;
    *) echo "unknown" ;;
  esac
}
OS="$(detect_os)"

# ── Load .env if present (for port defaults) ──────────────────────────────────
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set +a
  while IFS='=' read -r key value; do
    # Skip comments and blank lines
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    # Only load EMBEDINATOR_PORT_* and OLLAMA_MODELS from .env
    case "$key" in
      EMBEDINATOR_PORT_FRONTEND|EMBEDINATOR_PORT_BACKEND|EMBEDINATOR_PORT_QDRANT|EMBEDINATOR_PORT_QDRANT_GRPC|EMBEDINATOR_PORT_OLLAMA|OLLAMA_MODELS|EMBEDINATOR_GPU)
        # Don't override if already set in environment
        if [[ -z "${!key:-}" ]]; then
          export "$key=$value"
        fi
        ;;
    esac
  done < .env
fi

# Re-apply defaults after .env load
FRONTEND_PORT="${EMBEDINATOR_PORT_FRONTEND:-3000}"
BACKEND_PORT="${EMBEDINATOR_PORT_BACKEND:-8000}"
QDRANT_PORT="${EMBEDINATOR_PORT_QDRANT:-6333}"
QDRANT_GRPC_PORT="${EMBEDINATOR_PORT_QDRANT_GRPC:-6334}"
OLLAMA_PORT="${EMBEDINATOR_PORT_OLLAMA:-11434}"
OLLAMA_MODELS="${OLLAMA_MODELS:-qwen2.5:7b,nomic-embed-text}"

# ── Apply CLI port overrides (highest precedence) ─────────────────────────────
if [[ -n "$CLI_FRONTEND_PORT" ]]; then
  FRONTEND_PORT="$CLI_FRONTEND_PORT"
  export EMBEDINATOR_PORT_FRONTEND="$CLI_FRONTEND_PORT"
fi
if [[ -n "$CLI_BACKEND_PORT" ]]; then
  BACKEND_PORT="$CLI_BACKEND_PORT"
  export EMBEDINATOR_PORT_BACKEND="$CLI_BACKEND_PORT"
fi

# Export all ports for Docker Compose interpolation
export EMBEDINATOR_PORT_FRONTEND="$FRONTEND_PORT"
export EMBEDINATOR_PORT_BACKEND="$BACKEND_PORT"
export EMBEDINATOR_PORT_QDRANT="$QDRANT_PORT"
export EMBEDINATOR_PORT_QDRANT_GRPC="$QDRANT_GRPC_PORT"
export EMBEDINATOR_PORT_OLLAMA="$OLLAMA_PORT"

# ── Build compose file list ───────────────────────────────────────────────────
build_compose_args() {
  local gpu_profile="$1"
  local dev_mode="$2"
  local args="-f docker-compose.yml"

  case "$gpu_profile" in
    nvidia) args="$args -f docker-compose.gpu-nvidia.yml" ;;
    amd)    args="$args -f docker-compose.gpu-amd.yml" ;;
    intel)  args="$args -f docker-compose.gpu-intel.yml" ;;
  esac

  if [[ "$dev_mode" == "true" ]]; then
    args="$args -f docker-compose.dev.yml"
  fi

  echo "$args"
}

# ── GPU detection ─────────────────────────────────────────────────────────────
detect_gpu() {
  # macOS: always CPU
  if [[ "$OS" == "macos" ]]; then
    info "macOS detected — using CPU mode for Docker (no GPU passthrough in Docker Desktop)."
    info "For GPU-accelerated inference on macOS, install Ollama natively: https://ollama.com"
    echo "none"
    return
  fi

  # Env var override
  if [[ -n "${EMBEDINATOR_GPU:-}" ]]; then
    case "${EMBEDINATOR_GPU}" in
      nvidia|amd|intel|none)
        info "GPU override: EMBEDINATOR_GPU=${EMBEDINATOR_GPU}"
        echo "${EMBEDINATOR_GPU}"
        return ;;
      *)
        warn "Invalid EMBEDINATOR_GPU value '${EMBEDINATOR_GPU}'. Valid: nvidia|amd|intel|none. Falling back to auto-detect."
        ;;
    esac
  fi

  # NVIDIA: nvidia-smi available AND docker runtime has nvidia
  if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
    if docker info 2>/dev/null | grep -qi "nvidia"; then
      info "NVIDIA GPU detected with Docker runtime support."
      echo "nvidia"
      return
    else
      warn "nvidia-smi found but NVIDIA Docker runtime not configured. Falling back to CPU."
      warn "To enable: install nvidia-container-toolkit and run 'sudo nvidia-ctk runtime configure --runtime=docker'"
    fi
  fi

  # AMD: /dev/kfd exists AND rocminfo available
  if [[ -e /dev/kfd ]] && command -v rocminfo &>/dev/null && rocminfo &>/dev/null 2>&1; then
    info "AMD ROCm GPU detected."
    echo "amd"
    return
  fi

  # Intel: /dev/dri/renderD* exists
  if ls /dev/dri/renderD* &>/dev/null 2>&1; then
    info "Intel GPU detected (experimental)."
    echo "intel"
    return
  fi

  info "No supported GPU detected — using CPU mode."
  echo "none"
}

# ── Host Ollama conflict detection ────────────────────────────────────────────
# The Embedinator runs Ollama exclusively in Docker. This function blocks
# startup if a host-native ollama daemon (or any other non-Docker process) is
# holding port 11434, so Docker Ollama can always bind cleanly.
check_host_ollama_conflict() {
  # If our Docker Ollama container is already running, the port is ours — OK.
  if docker ps --filter 'name=embedinator-ollama' --filter 'status=running' --format '{{.Names}}' 2>/dev/null | grep -q '.'; then
    return 0
  fi

  # Is anything listening on :11434?
  local bound=false
  if command -v lsof &>/dev/null && lsof -iTCP:11434 -sTCP:LISTEN -n -P &>/dev/null 2>&1; then
    bound=true
  elif command -v ss &>/dev/null && ss -tln 2>/dev/null | awk '{print $4}' | grep -Eq '(^|:)11434$'; then
    bound=true
  fi
  $bound || return 0

  # Port is bound and it's not our container. Identify the owner for the
  # error message (best-effort — not required for the block to trigger).
  local owner="unknown"
  if pgrep -f 'ollama serve' &>/dev/null 2>&1; then
    owner="host-native ollama daemon"
  elif command -v lsof &>/dev/null; then
    local pid
    pid=$(lsof -tiTCP:11434 -sTCP:LISTEN 2>/dev/null | head -1 || true)
    if [[ -n "$pid" ]]; then
      owner="PID $pid ($(ps -p "$pid" -o comm= 2>/dev/null || echo unknown))"
    fi
  fi

  error "Port 11434 (Ollama) is held by a non-Docker process: $owner"
  error ""
  error "  The Embedinator runs Ollama exclusively in Docker."
  error "  A host-native Ollama is interfering with startup."
  error ""
  error "  Stop and disable the host daemon:"
  error "    sudo systemctl stop ollama 2>/dev/null || pkill -f 'ollama serve'"
  error "    sudo systemctl disable ollama 2>/dev/null || true"
  error ""
  error "  The host 'ollama' CLI binary is harmless — only the daemon must"
  error "  be stopped. After stopping, re-run: ./embedinator.sh"
  exit 1
}

# ── Port conflict detection ───────────────────────────────────────────────────
check_port() {
  local port="$1"
  local name="$2"
  local suggestion="$3"

  if lsof -i ":${port}" &>/dev/null 2>&1; then
    local pid
    pid=$(lsof -ti ":${port}" 2>/dev/null | head -1 || true)
    local proc=""
    if [[ -n "$pid" ]]; then
      proc=" (PID $pid: $(ps -p "$pid" -o comm= 2>/dev/null || echo 'unknown'))"
    fi
    error "Port ${port} (${name}) is already in use${proc}."
    error "  Resolution: ./embedinator.sh ${suggestion}"
    return 1
  fi
  return 0
}

check_all_ports() {
  local failed=false

  check_port "$FRONTEND_PORT" "frontend" "--frontend-port <PORT>" || failed=true
  check_port "$BACKEND_PORT"  "backend"  "--backend-port <PORT>"  || failed=true
  check_port "$QDRANT_PORT"   "qdrant"   "--frontend-port <PORT> (or set EMBEDINATOR_PORT_QDRANT in .env)" || failed=true
  check_port "$OLLAMA_PORT"   "ollama"   "(set EMBEDINATOR_PORT_OLLAMA in .env)" || failed=true

  if $failed; then
    die "Port conflicts detected. Resolve them and retry."
  fi
}

# ── Preflight checks ──────────────────────────────────────────────────────────
preflight_checks() {
  info "Running preflight checks..."

  # 1. Docker daemon
  if ! docker info &>/dev/null 2>&1; then
    if [[ "$OS" == "linux" ]] || [[ "$OS" == "wsl2" ]]; then
      # Check Docker group membership (FR-054)
      if ! groups | grep -q docker 2>/dev/null; then
        error "Docker daemon is not accessible."
        error "Your user is not in the 'docker' group."
        error "  Fix: sudo usermod -aG docker \$USER && newgrp docker"
        error "  Then restart your terminal and retry."
        exit 1
      fi
    fi
    die "Docker daemon is not running. Please start Docker Desktop (or 'sudo systemctl start docker' on Linux)."
  fi

  # 2. Docker Compose v2
  if ! docker compose version &>/dev/null 2>&1; then
    die "Docker Compose v2 is not available. Please upgrade Docker Desktop or install 'docker compose' plugin.\n  See: https://docs.docker.com/compose/install/"
  fi

  # 3. Disk space warning (< 15GB)
  local available_kb
  available_kb=$(df -k . 2>/dev/null | awk 'NR==2 {print $4}' || echo 0)
  local available_gb=$(( available_kb / 1024 / 1024 ))
  if [[ $available_gb -lt 15 ]]; then
    warn "Low disk space: ${available_gb}GB available. At least 15GB recommended for Docker images and AI models."
  fi

  # 4. macOS Docker Desktop memory warning (FR-056)
  if [[ "$OS" == "macos" ]]; then
    local mem_mb
    mem_mb=$(docker info 2>/dev/null | grep "Total Memory" | grep -oE '[0-9]+(\.[0-9]+)?[GgMm]iB' | head -1 || echo "")
    if [[ -n "$mem_mb" ]]; then
      # Parse GiB value
      local mem_gib
      mem_gib=$(echo "$mem_mb" | grep -oE '[0-9]+(\.[0-9]+)?' | head -1 || echo "0")
      if echo "$mem_mb" | grep -qi "MiB"; then
        # Convert MiB to GiB for comparison (MiB < 4096 → < 4 GiB)
        local mem_mib_int
        mem_mib_int=$(echo "$mem_gib" | cut -d. -f1)
        if [[ $mem_mib_int -lt 4096 ]]; then
          warn "Docker Desktop has less than 4GB RAM allocated."
          warn "  AI models (qwen2.5:7b) require at least 4GB. Increase in Docker Desktop → Settings → Resources."
        fi
      else
        # It's GiB
        local mem_gib_int
        mem_gib_int=$(echo "$mem_gib" | cut -d. -f1)
        if [[ $mem_gib_int -lt 4 ]]; then
          warn "Docker Desktop has less than 4GB RAM allocated (${mem_gib}GiB)."
          warn "  AI models (qwen2.5:7b) require at least 4GB. Increase in Docker Desktop → Settings → Resources."
        fi
      fi
    fi
  fi

  # 5. WSL2 path warning (FR-055)
  if [[ "$OS" == "wsl2" ]]; then
    if [[ "$PWD" == /mnt/c/* ]] || [[ "$PWD" == /mnt/[a-z]/* ]]; then
      warn "You are running from a Windows filesystem path (${PWD})."
      warn "  This causes significant I/O performance degradation."
      warn "  Recommended: clone the repo to your WSL2 home directory (e.g. ~/projects/The-Embedinator)"
      warn "  and run the launcher from there."
    fi
  fi

  success "Preflight checks passed."
}

# ── .env generation ───────────────────────────────────────────────────────────
generate_env() {
  if [[ -f .env ]]; then
    return 0
  fi

  if [[ ! -f .env.example ]]; then
    die ".env.example not found. Please run this script from the repository root."
  fi

  info "First run: generating .env from .env.example..."
  cp .env.example .env

  info "Generating Fernet encryption key (using Docker — no local Python required)..."
  local fernet_key
  fernet_key=$(docker run --rm python:3.14-slim python -c \
    "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null) || \
    die "Failed to generate Fernet key. Ensure Docker can pull 'python:3.14-slim' (check internet connection)."

  if [[ -z "$fernet_key" ]]; then
    die "Fernet key generation returned empty output. Check Docker network connectivity."
  fi

  # Inject key into .env (replace empty value)
  if grep -q "^EMBEDINATOR_FERNET_KEY=" .env; then
    sed -i "s|^EMBEDINATOR_FERNET_KEY=.*|EMBEDINATOR_FERNET_KEY=${fernet_key}|" .env
  else
    echo "EMBEDINATOR_FERNET_KEY=${fernet_key}" >> .env
  fi

  success "Generated .env with Fernet key."
  FIRST_RUN=true
}

# ── CORS auto-detection ───────────────────────────────────────────────────────
update_cors() {
  local lan_ip=""

  if [[ "$OS" == "macos" ]]; then
    lan_ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)
  else
    lan_ip=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
  fi

  local cors_value="http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}"
  if [[ -n "$lan_ip" && "$lan_ip" != "127.0.0.1" ]]; then
    cors_value="${cors_value},http://${lan_ip}:${FRONTEND_PORT}"
  fi

  if grep -q "^CORS_ORIGINS=" .env; then
    sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=${cors_value}|" .env
  else
    echo "CORS_ORIGINS=${cors_value}" >> .env
  fi
}

# ── Data directories ──────────────────────────────────────────────────────────
create_data_dirs() {
  mkdir -p data/uploads data/qdrant_db
}

# ── Idempotency check ─────────────────────────────────────────────────────────
FIRST_RUN=false

check_already_running() {
  # Check if any embedinator service is already running
  local running
  running=$(docker compose ps --format json 2>/dev/null | \
    python3 -c "import sys,json; data=sys.stdin.read().strip(); items=[json.loads(l) for l in data.splitlines() if l.strip()]; running=[i for i in items if i.get('State','').lower() in ('running','restarting')]; print(len(running))" 2>/dev/null || \
    docker compose ps --quiet 2>/dev/null | wc -l | tr -d ' ' || echo "0")

  if [[ "$running" =~ ^[0-9]+$ ]] && [[ "$running" -gt 0 ]]; then
    return 0  # already running
  fi
  return 1  # not running
}

# ── Health polling ─────────────────────────────────────────────────────────────
# Returns 0 if healthy, 1 if not
poll_service() {
  local name="$1"
  local url="$2"
  curl -sf --max-time 3 "$url" &>/dev/null
}

poll_all_services() {
  local timeout="$1"
  local start elapsed
  start=$(date +%s)
  local qdrant_ok=false backend_ok=false ollama_ok=false frontend_ok=false
  local all_ok=false

  info "Waiting for services to be healthy (timeout: ${timeout}s)..."

  while true; do
    elapsed=$(( $(date +%s) - start ))
    if [[ $elapsed -ge $timeout ]]; then
      echo ""
      error "Timeout waiting for services after ${timeout}s."
      error "Check logs: ./embedinator.sh --logs"
      return 1
    fi

    $qdrant_ok  || poll_service "qdrant"   "http://localhost:${QDRANT_PORT}/healthz"        && qdrant_ok=true   || true
    $ollama_ok  || poll_service "ollama"   "http://localhost:${OLLAMA_PORT}/api/tags"        && ollama_ok=true   || true
    $backend_ok || poll_service "backend"  "http://localhost:${BACKEND_PORT}/api/health/live" && backend_ok=true || true
    $frontend_ok|| poll_service "frontend" "http://localhost:${FRONTEND_PORT}/healthz"       && frontend_ok=true || true

    local status_line=""
    status_line+=" qdrant:$(  $qdrant_ok   && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}…${NC}")"
    status_line+=" ollama:$(  $ollama_ok   && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}…${NC}")"
    status_line+=" backend:$( $backend_ok  && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}…${NC}")"
    status_line+=" frontend:$($frontend_ok && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}…${NC}")"

    printf "\r  [%3ds] %s" "$elapsed" "$status_line"

    if $qdrant_ok && $ollama_ok && $backend_ok && $frontend_ok; then
      all_ok=true
      break
    fi

    sleep 3
  done

  echo ""
  if $all_ok; then
    success "All services are healthy."
    return 0
  fi
  return 1
}

# ── Model pull ────────────────────────────────────────────────────────────────
pull_models() {
  info "Checking AI models..."
  local existing_models
  existing_models=$(docker compose exec ollama ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' || true)

  IFS=',' read -ra models <<< "$OLLAMA_MODELS"
  for model in "${models[@]}"; do
    model="$(echo "$model" | tr -d '[:space:]')"
    [[ -z "$model" ]] && continue

    if echo "$existing_models" | grep -q "^${model}"; then
      success "Model already downloaded: ${model}"
    else
      info "Pulling model: ${model} (this may take several minutes on first run)..."
      docker compose exec ollama ollama pull "$model" || \
        warn "Failed to pull model '${model}'. You can retry: docker compose exec ollama ollama pull ${model}"
    fi
  done
}

# ── Status subcommand ─────────────────────────────────────────────────────────
show_status() {
  echo -e "\n${BOLD}Service Health Status${NC}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  check_and_print() {
    local name="$1" url="$2" port="$3"
    local result
    if curl -sf --max-time 3 "$url" &>/dev/null; then
      printf "  %-12s ${GREEN}healthy${NC}   port %s\n" "$name" "$port"
    else
      printf "  %-12s ${RED}unreachable${NC} port %s\n" "$name" "$port"
    fi
  }

  check_and_print "qdrant"   "http://localhost:${QDRANT_PORT}/healthz"          "$QDRANT_PORT"
  check_and_print "ollama"   "http://localhost:${OLLAMA_PORT}/api/tags"          "$OLLAMA_PORT"
  check_and_print "backend"  "http://localhost:${BACKEND_PORT}/api/health/live"  "$BACKEND_PORT"
  check_and_print "frontend" "http://localhost:${FRONTEND_PORT}/healthz"         "$FRONTEND_PORT"
  echo ""
}

# ── Compose command builder ───────────────────────────────────────────────────
run_compose() {
  local compose_args="$1"
  shift
  # shellcheck disable=SC2086
  docker compose $compose_args "$@"
}

# ── Browser open ──────────────────────────────────────────────────────────────
open_browser() {
  local url="http://localhost:${FRONTEND_PORT}"
  info "Opening browser: ${url}"
  if [[ "$OS" == "macos" ]]; then
    open "$url" 2>/dev/null || true
  else
    xdg-open "$url" 2>/dev/null || \
    (command -v wslview &>/dev/null && wslview "$url") || \
    true
  fi
}

# ── Ready message ─────────────────────────────────────────────────────────────
print_ready() {
  echo ""
  echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}${BOLD}  The Embedinator is ready!${NC}"
  echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo -e "  ${BOLD}Application:${NC}  http://localhost:${FRONTEND_PORT}"
  echo -e "  ${BOLD}Backend API:${NC}  http://localhost:${BACKEND_PORT}/api/health"
  echo ""
  echo -e "  ${BOLD}View logs:${NC}    ./embedinator.sh --logs"
  echo -e "  ${BOLD}Stop:${NC}         ./embedinator.sh --stop"
  echo -e "  ${BOLD}Status:${NC}       ./embedinator.sh --status"
  echo ""
}

# ══════════════════════════════════════════════════════════════════════════════
# Subcommand dispatch
# ══════════════════════════════════════════════════════════════════════════════

# --stop
if $CMD_STOP; then
  info "Stopping all services..."
  GPU_PROFILE="$(detect_gpu 2>/dev/null || echo none)"
  COMPOSE_ARGS="$(build_compose_args "$GPU_PROFILE" "$CMD_DEV")"
  # shellcheck disable=SC2086
  run_compose "$COMPOSE_ARGS" down
  success "All services stopped."
  exit 0
fi

# --restart: stop first, then fall through to start
if $CMD_RESTART; then
  info "Restarting all services..."
  GPU_PROFILE="$(detect_gpu 2>/dev/null || echo none)"
  COMPOSE_ARGS="$(build_compose_args "$GPU_PROFILE" "$CMD_DEV")"
  # shellcheck disable=SC2086
  run_compose "$COMPOSE_ARGS" down
  success "Services stopped. Starting again..."
  # Fall through to start flow below
fi

# --logs
if $CMD_LOGS; then
  GPU_PROFILE="$(detect_gpu 2>/dev/null || echo none)"
  COMPOSE_ARGS="$(build_compose_args "$GPU_PROFILE" "$CMD_DEV")"
  if [[ -n "$LOGS_SERVICE" ]]; then
    # shellcheck disable=SC2086
    run_compose "$COMPOSE_ARGS" logs -f "$LOGS_SERVICE"
  else
    # shellcheck disable=SC2086
    run_compose "$COMPOSE_ARGS" logs -f
  fi
  exit 0
fi

# --status
if $CMD_STATUS; then
  show_status
  exit 0
fi

# ══════════════════════════════════════════════════════════════════════════════
# Start flow (default, --dev, --restart fall-through)
# ══════════════════════════════════════════════════════════════════════════════

echo -e "${BOLD}The Embedinator — Starting up${NC}"
echo ""

preflight_checks

# Block early if a host-native Ollama is conflicting with Docker Ollama.
check_host_ollama_conflict

# Detect GPU profile
GPU_PROFILE="$(detect_gpu)"
info "GPU profile: ${GPU_PROFILE}"

COMPOSE_ARGS="$(build_compose_args "$GPU_PROFILE" "$CMD_DEV")"

# Check ports before starting
check_all_ports

# Generate .env if needed
generate_env

# Update CORS origins
update_cors

# Create data directories
create_data_dirs

# Idempotency check
if check_already_running; then
  warn "Services are already running. Reporting status instead of starting duplicate containers."
  show_status
  exit 0
fi

# Determine timeout: 300s first run, 60s subsequent
HEALTH_TIMEOUT=60
if $FIRST_RUN; then
  HEALTH_TIMEOUT=300
  info "First run detected — using extended timeout (${HEALTH_TIMEOUT}s) for image builds and model downloads."
fi

# Start compose
if $CMD_DEV; then
  info "Starting in developer mode (hot reload)..."
else
  info "Starting services..."
fi

# shellcheck disable=SC2086
run_compose "$COMPOSE_ARGS" up --build -d

# Poll health endpoints
poll_all_services "$HEALTH_TIMEOUT"

# Pull missing models
pull_models

# Open browser if requested
if $CMD_OPEN; then
  open_browser
fi

# Print ready message
print_ready
