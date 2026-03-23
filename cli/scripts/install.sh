#!/usr/bin/env bash
# install.sh — one-liner installer for The Embedinator CLI
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Bruno-Ghiberto/The-Embedinator/main/cli/scripts/install.sh | bash
#
# Install a specific version:
#   curl -fsSL https://raw.githubusercontent.com/Bruno-Ghiberto/The-Embedinator/main/cli/scripts/install.sh | bash -s -- --version 0.1.0
#
# The script will install the embedinator binary to /usr/local/bin (or ~/.local/bin
# if /usr/local/bin is not writable), verify the SHA-256 checksum, and print next steps.

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO="Bruno-Ghiberto/The-Embedinator"
BINARY_NAME="embedinator"
RELEASES_API="https://api.github.com/repos/${REPO}/releases"
GITHUB_DL_BASE="https://github.com/${REPO}/releases/download"

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && tput colors >/dev/null 2>&1; then
  RED=$(tput setaf 1)
  GREEN=$(tput setaf 2)
  YELLOW=$(tput setaf 3)
  CYAN=$(tput setaf 6)
  BOLD=$(tput bold)
  RESET=$(tput sgr0)
else
  RED=""
  GREEN=""
  YELLOW=""
  CYAN=""
  BOLD=""
  RESET=""
fi

info()    { printf "${CYAN}[embedinator]${RESET} %s\n" "$*"; }
success() { printf "${GREEN}[embedinator]${RESET} ${BOLD}%s${RESET}\n" "$*"; }
warn()    { printf "${YELLOW}[embedinator] WARNING:${RESET} %s\n" "$*" >&2; }
error()   { printf "${RED}[embedinator] ERROR:${RESET} %s\n" "$*" >&2; }
die()     { error "$*"; exit 1; }

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
detect_os() {
  case "$(uname -s)" in
    Linux*)   echo "linux"  ;;
    Darwin*)  echo "darwin" ;;
    *)        die "Unsupported OS: $(uname -s). Use the Windows PowerShell installer for Windows." ;;
  esac
}

detect_arch() {
  case "$(uname -m)" in
    x86_64)          echo "amd64" ;;
    amd64)           echo "amd64" ;;
    aarch64|arm64)   echo "arm64" ;;
    *)               die "Unsupported architecture: $(uname -m). Only amd64 and arm64 are supported." ;;
  esac
}

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "Required command not found: $1. Please install it and try again."
  fi
}

# ---------------------------------------------------------------------------
# HTTP fetch helper (curl preferred, wget fallback)
# ---------------------------------------------------------------------------
http_get() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --max-time 15 "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- --timeout=15 "$url"
  else
    die "Neither curl nor wget is available. Install one and try again."
  fi
}

# ---------------------------------------------------------------------------
# GitHub Releases API: find latest cli/v* tag
# ---------------------------------------------------------------------------
get_latest_version() {
  local url="${RELEASES_API}?per_page=50"
  local response
  response=$(http_get "$url") \
    || die "Failed to query GitHub Releases API. Check your internet connection."

  local version=""

  # Prefer jq for robust JSON parsing if available
  if command -v jq >/dev/null 2>&1; then
    version=$(printf '%s' "$response" \
      | jq -r '[.[] | select(.tag_name | startswith("cli/v"))][0].tag_name // empty' \
      | sed 's|^cli/v||') || true
  fi

  # Fallback to grep/sed when jq is not installed
  if [ -z "$version" ]; then
    version=$(printf '%s' "$response" \
      | grep '"tag_name"' \
      | grep '"cli/v' \
      | head -n1 \
      | sed -E 's/.*"cli\/v([^"]+)".*/\1/') \
      || true
  fi

  if [ -z "$version" ]; then
    die "Could not determine the latest CLI version from GitHub Releases. \
Try again later or download manually from: https://github.com/${REPO}/releases"
  fi

  echo "$version"
}

# ---------------------------------------------------------------------------
# Download helper (curl preferred, wget fallback)
# ---------------------------------------------------------------------------
download() {
  local url="$1"
  local dest="$2"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --max-time 120 --progress-bar -o "$dest" "$url" \
      || die "Download failed: ${url}"
  elif command -v wget >/dev/null 2>&1; then
    wget -q --timeout=120 --show-progress -O "$dest" "$url" \
      || die "Download failed: ${url}"
  else
    die "Neither curl nor wget is available."
  fi
}

# ---------------------------------------------------------------------------
# SHA-256 checksum verification
# ---------------------------------------------------------------------------
verify_checksum() {
  local archive="$1"
  local checksums_file="$2"
  local archive_basename
  archive_basename="$(basename "$archive")"

  local expected_hash
  expected_hash=$(grep "  ${archive_basename}$" "$checksums_file" | awk '{print $1}') || true

  if [ -z "$expected_hash" ]; then
    die "Checksum entry not found for ${archive_basename} in checksums.txt"
  fi

  local actual_hash
  if command -v sha256sum >/dev/null 2>&1; then
    actual_hash=$(sha256sum "$archive" | awk '{print $1}')
  elif command -v shasum >/dev/null 2>&1; then
    actual_hash=$(shasum -a 256 "$archive" | awk '{print $1}')
  else
    warn "No sha256sum or shasum found — skipping checksum verification."
    return 0
  fi

  if [ "$actual_hash" != "$expected_hash" ]; then
    die "Checksum mismatch for ${archive_basename}.
  Expected: ${expected_hash}
  Got:      ${actual_hash}
The downloaded file may be corrupted or tampered with. Aborting installation."
  fi

  success "Checksum verified."
}

# ---------------------------------------------------------------------------
# Install directory selection
# ---------------------------------------------------------------------------
choose_install_dir() {
  if [ -w "/usr/local/bin" ]; then
    echo "/usr/local/bin"
  elif [ -d "$HOME/.local/bin" ] || mkdir -p "$HOME/.local/bin" 2>/dev/null; then
    echo "$HOME/.local/bin"
  else
    die "Cannot determine a writable install directory. \
Try running with sudo, or create ~/.local/bin and try again."
  fi
}

# ---------------------------------------------------------------------------
# PATH check and instructions
# ---------------------------------------------------------------------------
check_path() {
  local install_dir="$1"
  case ":${PATH}:" in
    *":${install_dir}:"*)
      return 0
      ;;
  esac

  warn "${install_dir} is not in your PATH."
  printf "\n"
  printf "  Add the following line to your shell profile:\n\n"
  case "${SHELL:-}" in
    */fish)
      printf "    fish_add_path %s\n" "$install_dir"
      ;;
    */zsh)
      printf "    echo 'export PATH=\"%s:\$PATH\"' >> ~/.zshrc && source ~/.zshrc\n" "$install_dir"
      ;;
    *)
      printf "    echo 'export PATH=\"%s:\$PATH\"' >> ~/.bashrc && source ~/.bashrc\n" "$install_dir"
      ;;
  esac
  printf "\n"
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
REQUESTED_VERSION=""

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --version|-v)
        if [ $# -lt 2 ]; then
          die "--version requires a value (e.g., --version 0.1.0)"
        fi
        REQUESTED_VERSION="$2"
        shift 2
        ;;
      --version=*)
        REQUESTED_VERSION="${1#--version=}"
        shift
        ;;
      --help|-h)
        printf "Usage: install.sh [--version <VERSION>]\n\n"
        printf "Options:\n"
        printf "  --version, -v    Install a specific version (e.g., 0.1.0)\n"
        printf "  --help, -h       Show this help message\n"
        exit 0
        ;;
      *)
        die "Unknown option: $1. Use --help for usage."
        ;;
    esac
  done
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  parse_args "$@"

  printf "\n"
  info "Installing The Embedinator CLI..."
  printf "\n"

  # Dependency checks
  require_cmd uname

  local os arch
  os="$(detect_os)"
  arch="$(detect_arch)"

  info "Detected platform: ${BOLD}${os}/${arch}${RESET}"

  # Resolve version
  local version
  if [ -n "$REQUESTED_VERSION" ]; then
    # Strip leading 'v' if provided (e.g., v0.1.0 -> 0.1.0)
    version="${REQUESTED_VERSION#v}"
    info "Requested version: ${BOLD}v${version}${RESET}"
  else
    info "Checking latest release..."
    version="$(get_latest_version)"
    info "Latest version: ${BOLD}v${version}${RESET}"
  fi

  # Build asset names
  local archive_name="embedinator_v${version}_${os}_${arch}.tar.gz"
  local tag="cli/v${version}"
  local download_url="${GITHUB_DL_BASE}/${tag}/${archive_name}"
  local checksums_url="${GITHUB_DL_BASE}/${tag}/checksums.txt"

  # Temporary working directory (cleaned up on exit)
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "${tmpdir}"' EXIT

  local archive_path="${tmpdir}/${archive_name}"
  local checksums_path="${tmpdir}/checksums.txt"

  # Download archive and checksums
  info "Downloading ${archive_name}..."
  download "$download_url" "$archive_path"

  info "Downloading checksums..."
  download "$checksums_url" "$checksums_path"

  # Verify checksum
  info "Verifying checksum..."
  verify_checksum "$archive_path" "$checksums_path"

  # Extract binary
  info "Extracting binary..."
  tar -xzf "$archive_path" -C "$tmpdir" \
    || die "Failed to extract ${archive_name}"

  local extracted_binary="${tmpdir}/${BINARY_NAME}"
  if [ ! -f "$extracted_binary" ]; then
    die "Expected binary '${BINARY_NAME}' not found in archive. Contents: $(ls "${tmpdir}")"
  fi

  # Make binary executable
  chmod +x "$extracted_binary"

  # Choose install directory and install
  local install_dir
  install_dir="$(choose_install_dir)"
  local install_path="${install_dir}/${BINARY_NAME}"

  info "Installing to ${BOLD}${install_path}${RESET}..."
  if [ -w "$install_dir" ]; then
    install -m 755 "$extracted_binary" "$install_path" \
      || die "Failed to install binary to ${install_path}"
  else
    # Need sudo for /usr/local/bin
    warn "Root privileges required to write to ${install_dir}."
    sudo install -m 755 "$extracted_binary" "$install_path" \
      || die "Failed to install binary to ${install_path} (sudo failed)"
  fi

  # Verify installation
  if ! "$install_path" version >/dev/null 2>&1; then
    warn "Binary installed but 'embedinator version' exited with an error. \
This may be harmless if the binary needs a terminal."
  fi

  printf "\n"
  success "The Embedinator CLI v${version} installed successfully!"
  printf "\n"

  # PATH check
  check_path "$install_dir"

  # Next steps
  printf "  ${BOLD}Next steps:${RESET}\n\n"
  printf "    1. Clone or enter the project directory\n"
  printf "    2. Run: ${CYAN}${BOLD}embedinator${RESET}\n"
  printf "       (First run launches the setup wizard)\n\n"
  printf "  ${BOLD}Common commands:${RESET}\n\n"
  printf "    embedinator           Run setup wizard (first time) or start services\n"
  printf "    embedinator start     Start all services\n"
  printf "    embedinator stop      Stop all services\n"
  printf "    embedinator status    Show service health\n"
  printf "    embedinator doctor    Diagnose common problems\n\n"
  printf "  ${BOLD}Documentation:${RESET}\n"
  printf "    https://github.com/${REPO}\n\n"
}

main "$@"
