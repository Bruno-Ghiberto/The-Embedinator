# Design Analysis: TUI Installer v2

**Date**: 2026-03-23
**Status**: Analysis and Design (no code changes)
**Scope**: `cli/` Go module -- port selection UX, tool completeness, distribution strategy
**Input artifacts**: `docs/design-tui-installer.md` (1935 lines), `docs/design-launcher-improvements.md` (655 lines), full `cli/` source tree (37 Go files + 2 install scripts + goreleaser config)
**Constraint**: Makefile is SACRED -- zero changes.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Port Selection Design](#2-port-selection-design)
3. [Tool Analysis](#3-tool-analysis)
4. [Distribution Strategy](#4-distribution-strategy)
5. [Recommendations](#5-recommendations)
6. [Architecture Diagram](#6-architecture-diagram)

---

## 1. Executive Summary

### Current State Assessment

The `cli/` module is a well-structured Go application with a clear three-layer architecture: Cobra CLI layer, Bubbletea TUI wizard layer, and a pure-logic engine layer. The codebase covers all 10 wizard screens, 12 Cobra subcommands, 11 engine modules, cross-platform install scripts, and a goreleaser config for 6 build targets.

**Overall readiness: 75-80%.** The architecture is sound and the critical path (welcome -> preflight -> ollama -> ports -> GPU -> models -> API keys -> summary -> progress -> complete) is wired end-to-end. However, several areas need work before this can ship to real users.

### Critical Finding: Port Selection UX

The port selection screen currently **auto-assigns** ports silently without user choice. When a conflict is detected, `autoResolveConflicts()` finds the next available port and applies it immediately. The user sees a message "Some ports were auto-resolved to next available port" and can only press Enter to continue.

This directly violates the user's requirement that **users MUST be able to CHOOSE which ports each service uses**. The design doc (section 4.4) specifies an interactive resolution flow with three options (use suggested port / enter custom / skip), but the implementation skips all of that.

### Top 5 Issues by Priority

| # | Issue | Severity | Module |
|---|-------|----------|--------|
| 1 | Port screen auto-resolves without user choice | **Critical** | `wizard/ports.go` |
| 2 | API key screen does not capture actual key input | Medium | `wizard/apikeys.go` |
| 3 | Self-update does not extract archive before replacing | Medium | `engine/selfupdate.go` |
| 4 | Non-interactive setup path is a no-op (runs wizard anyway) | Medium | `cmd/setup.go` |
| 5 | No test files exist for any module | Low (pre-release) | entire `cli/` |

---

## 2. Port Selection Design

### 2.1 Current Behavior (Problem)

The implementation in `cli/internal/wizard/ports.go` lines 85-114 does this:

```
On Init():
  1. Call engine.CheckAllPorts(cfg) -- scan all 5 ports
  2. Receive portScanDoneMsg

On portScanDoneMsg:
  1. Check if all ports are available
  2. If any conflict: call autoResolveConflicts()
  3. autoResolveConflicts() silently finds next available port via engine.FindAvailablePort()
  4. Applies the new port to WizardState via applyPort()
  5. User sees only the result: "Some ports were auto-resolved to next available port."
  6. User presses Enter to continue -- no choice presented.
```

There is no interactive prompt, no custom port input, and no option to override auto-assignment. The user is a passive observer.

### 2.2 Design Doc Specification (from section 4.4)

The original design doc specifies this flow for each conflict:

```
  Port 11434 is in use. Choose a resolution:

  > Use next available port (11435)
    Enter a custom port
    Skip (I will resolve this myself)
```

This is the correct approach. Each conflict gets its own huh.Select form.

### 2.3 Proposed Port Selection UX

The port screen should have three distinct phases, managed by a `portPhase` enum:

**Phase 1: Scanning** (automatic, no interaction)
```
  Port Configuration

  Scanning ports for conflicts...

    Frontend (Next.js)    :3000   ... scanning
    Backend (FastAPI)     :8000   ... scanning
    Qdrant (vector DB)    :6333   ... scanning
    Qdrant gRPC           :6334   ... scanning
    Ollama                :11434  ... scanning
```

**Phase 2: Conflict Resolution** (interactive, one huh.Select per conflict)
```
  Port Configuration

    Frontend (Next.js)    :3000   available
    Backend (FastAPI)     :8000   in use (PID 12345: python)
    Qdrant (vector DB)    :6333   available
    Qdrant gRPC           :6334   available
    Ollama                :11434  skipped (using local)

  Port 8000 (Backend) is in use. Choose a resolution:

  > Use next available port: 8001
    Enter a custom port number
    Keep 8000 (I will free it myself)

  Use arrow keys to select, Enter to confirm.
```

If "Enter a custom port number" is selected, a huh.Input appears:

```
  Enter port number for Backend (FastAPI):
  > 9000

  Validating... available.
```

The custom port input validates:
- Numeric, in range 1024-65535
- Not currently in use (re-scanned at input time)
- Not conflicting with another Embedinator service port

**Phase 3: Port Review** (optional but recommended -- shows all final assignments)
```
  Port Configuration -- Final Assignment

    Frontend (Next.js)    :3000   available
    Backend (FastAPI)     :8001   available (changed from 8000)
    Qdrant (vector DB)    :6333   available
    Qdrant gRPC           :6334   available
    Ollama                :11434  skipped (using local)

  All ports confirmed.

  Press Enter to continue.
```

**Phase 2 is the key addition.** Without it, the user has no agency over port assignment. The auto-suggest is still present (as option 1 in the huh.Select), but the user explicitly chooses it rather than having it forced.

### 2.4 Bubbletea Model Design

The PortsModel needs to be refactored from a single-phase model to a multi-phase state machine:

```go
type portPhase int

const (
    portPhaseScanning   portPhase = iota  // Phase 1: running CheckAllPorts
    portPhaseResolving                     // Phase 2: showing huh.Select per conflict
    portPhaseCustomInput                   // Phase 2b: huh.Input for custom port
    portPhaseReview                        // Phase 3: final assignment review
)

type PortsModel struct {
    state         *WizardState
    portStatus    []engine.PortStatus
    phase         portPhase
    conflicts     []int               // indices into portStatus of conflicting ports
    conflictIdx   int                 // which conflict we are resolving now
    suggested     int                 // auto-suggested next available port for current conflict
    form          *huh.Form           // current resolution form (select or input)
    formDone      bool
    choice        string              // "suggested" | "custom" | "keep"
    customPort    string              // user-entered custom port (string for input field)
    width         int
}
```

The Update loop processes:
1. `portScanDoneMsg` -> identify conflicts, transition to `portPhaseResolving`
2. For each conflict: build a huh.Select with three options
3. On "suggested": apply suggested port, advance to next conflict
4. On "custom": transition to `portPhaseCustomInput`, show huh.Input with validation
5. On "keep": leave port unchanged, advance to next conflict
6. When all conflicts resolved: transition to `portPhaseReview`
7. On Enter in review phase: emit NextScreenMsg

### 2.5 Interaction with Ollama Mode

When `OllamaMode == "local"` and the Ollama port is in use, the port screen must NOT show a conflict resolution prompt for the Ollama port. This is already handled correctly in the current code (the "skipped (using local)" path). The new design preserves this: the Ollama port is excluded from the `conflicts` slice when local Ollama mode is active.

### 2.6 Edge Cases

**No conflicts at all:** Skip Phase 2 entirely. Phase 1 shows all green checkmarks, then Phase 3 (or directly NextScreenMsg).

**All 5 ports conflicting:** Phase 2 runs 5 sequential resolution prompts (or 4 if local Ollama). This is the worst case but still manageable since each prompt is one selection.

**User picks a port that conflicts with another Embedinator service:** The custom port validation must check against ALL currently assigned ports (including already-resolved ones), not just the default set. This is a cross-conflict validation that engine.ValidatePort already supports.

**User picks "keep" for a conflicting port:** Docker Compose will fail with "bind: address already in use" when it starts. The port screen should show a warning: "Warning: Port 8000 will conflict at startup. You must free it before running `embedinator start`."

---

## 3. Tool Analysis

### 3.1 cmd/ Layer (12 Cobra Commands)

| File | Command | Status | Issues |
|------|---------|--------|--------|
| `root.go` | `embedinator` (no args) | **Complete** | Smart default behavior (setup/start/status) is correctly implemented |
| `setup.go` | `embedinator setup` | **Incomplete** | Non-interactive mode is a no-op -- both branches call `wizard.Run(state)` identically |
| `start.go` | `embedinator start` | **Complete** | Health polling, timeout, --open flag all implemented |
| `stop.go` | `embedinator stop` | **Complete** | --volumes flag for destructive cleanup |
| `restart.go` | `embedinator restart` | **Complete** | Delegates to stop + start |
| `status.go` | `embedinator status` | **Complete** | JSON output + table display |
| `logs.go` | `embedinator logs` | **Complete** | Service filter, --tail, --since |
| `config_cmd.go` | `embedinator config` | **Complete** | Pre-populates from existing config.yaml |
| `doctor.go` | `embedinator doctor` | **Complete** | System, config, service checks + JSON output |
| `version_cmd.go` | `embedinator version` | **Complete** | Version/commit/date from ldflags |
| `completion.go` | `embedinator completion` | **Complete** | bash/zsh/fish/powershell |
| `update.go` | `embedinator update` | **Functional but incomplete** | Self-update does not extract the archive (see section 3.3) |

**setup.go issue detail:** Lines 34-41 show that both interactive and non-interactive paths call `wizard.Run(state)`. The non-interactive path should bypass the wizard entirely and call engine functions directly (generate .env, write config, compose up, health poll, model pull) using default or config.yaml values. This is a design gap, not just a code gap.

### 3.2 internal/wizard/ Layer (13 Files)

| File | Screen | Status | Issues |
|------|--------|--------|--------|
| `wizard.go` | Orchestrator | **Complete** | Screen flow, GoBackMsg, config-only wizard |
| `state.go` | WizardState | **Complete** | ToConfig(), DefaultWizardState() |
| `styles.go` | Brand theme | **Complete** | Colors, boxes, marks, ASCII art |
| `welcome.go` | Screen 1 | **Complete** | Large/small layout, gorilla art |
| `prerequisites.go` | Screen 2 | **Complete** | Spinner, retry on failure |
| `ollama.go` | Screen 3 | **Mostly complete** | Remote URL input is a placeholder (line 96: hardcoded `http://localhost:11434`) |
| `ports.go` | Screen 4 | **Critical gap** | Auto-resolves without user choice (see Section 2) |
| `gpu.go` | Screen 5 | **Complete** | Full diagnostic chain, issue display, form selection |
| `models.go` | Screen 6 | **Complete** | Multi-select with metadata, size estimates |
| `apikeys.go` | Screen 7 | **Incomplete** | Provider selection works but actual key input is not implemented (line 82: comment says "For now, skip API key entry") |
| `summary.go` | Screen 8 | **Complete** | Summary table, confirm/edit/abort |
| `progress.go` | Screen 9 | **Complete** | Compose up, health poll, model pull, elapsed timer |
| `complete.go` | Screen 10 | **Complete** | Success display, browser open |

**apikeys.go issue detail:** The screen lets users select a provider but never shows a huh.Input for the actual API key. After selection, it immediately advances to the next screen. The state fields (OpenAIKey, AnthropicKey, OpenRouterKey) are never populated. Additionally, there is dead code: a multi-select approach (providerSelect, lines 27-35) is defined but assigned to `_` (unused).

**ollama.go issue detail:** When "remote" mode is selected, the code should show a huh.Input for the remote URL with validation (HTTP/HTTPS URL format, reachability check). Currently line 96 hardcodes `http://localhost:11434` as a placeholder.

### 3.3 internal/engine/ Layer (11 Files)

| File | Responsibility | Status | Issues |
|------|---------------|--------|--------|
| `config.go` | config.yaml R/W | **Complete** | Atomic write, validation, defaults |
| `docker.go` | Compose operations | **Complete** | Engine socket targeting on Linux, health polling |
| `dotenv.go` | .env generation | **Complete** | Preserves unmanaged vars, atomic write |
| `gpu.go` | GPU diagnostics | **Complete** | NVIDIA/AMD/Intel chains, Docker Desktop coexistence, distro-specific commands |
| `ollama.go` | Local Ollama detection | **Complete** | Process check, API probe, model list |
| `overlay.go` | Compose overlay files | **Complete** | local-ollama, GPU overlays, atomic write |
| `ports.go` | Port scanning | **Complete** | ScanPort, FindAvailablePort, ValidatePort |
| `preflight.go` | System checks | **Complete** | Docker, Compose, disk, RAM, Docker type detection, distro detection |
| `selfupdate.go` | Binary self-update | **Incomplete** | Downloads the .tar.gz/.zip archive but does not extract it before os.Rename (line 106). The rename replaces the binary with a compressed archive, corrupting it. |
| `sysinfo.go` | OS/arch detection | **Complete** | WSL2, LAN IP |
| `version/version.go` | Build-time version | **Complete** | ldflags injection |

**selfupdate.go issue detail:** The DownloadUpdate function downloads the archive (.tar.gz or .zip) to a temp file. ApplySelfUpdate then does `os.Rename(newBinaryPath, execPath)`. This renames the ARCHIVE file over the binary, not the EXTRACTED binary. The archive must be extracted first, the binary found inside, and then renamed. This would corrupt the installation on every update.

### 3.4 Go Module Configuration

**go.mod analysis:**

```
module github.com/Bruno-Ghiberto/The-Embedinator/cli
go 1.24.2
```

The Go version is set to 1.24.2, which is correct and recent. The design doc mentions Go 1.23+ as the minimum; 1.24.2 exceeds this.

**Dependencies audit:**

| Dependency | Version | Purpose | Status |
|------------|---------|---------|--------|
| `charmbracelet/bubbles` | v1.0.0 | Pre-built TUI components | Current |
| `charmbracelet/bubbletea` | v1.3.10 | TUI framework | Current |
| `charmbracelet/huh` | v1.0.0 | Form-based wizard screens | Current |
| `charmbracelet/lipgloss` | v1.1.0 | Terminal styling | Current |
| `spf13/cobra` | v1.10.2 | CLI subcommands | Current |
| `gopkg.in/yaml.v3` | v3.0.1 | config.yaml R/W | Current |

**Missing dependency:** The design doc (section 2) mentions `docker/docker` as the Docker Engine API client library. It is not in go.mod. The current implementation uses `os/exec` to shell out to the `docker` CLI instead. This is acceptable for v1 but has limitations: no structured output parsing, no streaming event API, and subprocess overhead on every operation. The engine already wraps all Docker calls through `DockerCommand()`, so migrating to the Docker SDK later would be localized.

**Missing dependency:** No testing framework beyond stdlib. The design doc lists `_test.go` files for every engine package, but none exist in the actual codebase. All testing infrastructure is absent.

### 3.5 GoReleaser Configuration

**Platform coverage:**

| OS | Architecture | Format | Status |
|----|-------------|--------|--------|
| linux | amd64 | tar.gz | Covered |
| linux | arm64 | tar.gz | Covered |
| darwin | amd64 | tar.gz | Covered |
| darwin | arm64 | tar.gz | Covered |
| windows | amd64 | zip | Covered |
| windows | arm64 | zip | Covered |

All 6 targets are covered. CGO_ENABLED=0 ensures static linking.

**Issues found:**

1. **Archive `files` stanza:** The current config has `files: - none*` which is a glob that intentionally matches nothing (only the binary is included). This is correct.

2. **Homebrew tap:** The `brews` section references `HOMEBREW_TAP_TOKEN` env var and targets `Bruno-Ghiberto/homebrew-tap` repo. This repo does not exist yet -- it must be created before the first release.

3. **Tag format:** The goreleaser comment says `cli/v<semver>` tag format. The install scripts also look for `cli/v*` tags. This is consistent but means the project will have two tag namespaces: `v*` for the main project (currently v0.2.0) and `cli/v*` for the CLI binary. This is fine for a monorepo.

4. **`skip_upload: auto`:** Homebrew formula upload is auto-skipped for pre-releases. This is correct behavior.

5. **`release.extra_files`:** Install scripts are attached to the GitHub Release as downloadable assets. This is important for the `curl|sh` and `irm|iex` flows that download from raw.githubusercontent.com.

### 3.6 Install Scripts

**install.sh (Linux/macOS):**

- Structure: Complete and well-written. Color output, platform detection, checksum verification, sudo fallback, PATH check.
- Issues:
  - Line 93-98: Uses `grep` and `sed` to parse JSON from the GitHub API. This is fragile -- a single format change breaks it. Should use `jq` if available, with the current approach as fallback.
  - The script downloads from the `cli/v*` tag namespace, which is correct and consistent with goreleaser.
  - No GPG signature verification (only SHA-256 checksum). Acceptable for v1 but should be noted.

**install.ps1 (Windows):**

- Structure: Complete and well-written. BITS transfer with fallback, SHA-256 verification, PATH registry update with WM_SETTINGCHANGE broadcast.
- Issues:
  - Line 66: `Invoke-RestMethod` with `-UseBasicParsing` flag. UseBasicParsing is for `Invoke-WebRequest`, not `Invoke-RestMethod`. It will be ignored silently but should be removed for correctness.
  - PATH update via registry + SendMessageTimeout is the correct Windows pattern.
  - No elevation prompt -- installs to user-local directory, which is the right approach.

### 3.7 Missing Components Identified in Design Doc But Not Implemented

| Component | Design Doc Section | Priority |
|-----------|-------------------|----------|
| `_test.go` files for all engine packages | Section 7.1 | Medium (pre-release) |
| `.github/workflows/release-cli.yml` | Section 8.2 | High (required for distribution) |
| `.github/workflows/ci-cli.yml` | Section 8.3 | High (required for quality) |
| `homebrew-tap` repository | Section 3.3 | High (required for Homebrew) |
| Non-interactive setup mode | Section 5.3 | Medium |
| Remote Ollama URL input | Section 4.3 | Medium |
| API key actual input fields | Section 4.7 | Medium |
| Fernet key generation (Go-native or Docker-based) | Section 6.2 | High (required for .env) |

---

## 4. Distribution Strategy

### 4.1 Overview

The distribution strategy is a multi-channel approach where goreleaser is the single source of truth for building and publishing artifacts. Every channel ultimately resolves to a pre-built binary from a GitHub Release.

### 4.2 Installation Matrix

| Platform | Primary Method | Secondary Method | Fallback |
|----------|---------------|-----------------|----------|
| macOS (Apple Silicon) | `brew install Bruno-Ghiberto/tap/embedinator` | `curl -fsSL .../install.sh \| bash` | Direct download from GitHub Releases |
| macOS (Intel) | `brew install Bruno-Ghiberto/tap/embedinator` | `curl -fsSL .../install.sh \| bash` | Direct download |
| Linux (amd64) | `curl -fsSL .../install.sh \| bash` | `brew install Bruno-Ghiberto/tap/embedinator` | Direct download |
| Linux (arm64) | `curl -fsSL .../install.sh \| bash` | `brew install Bruno-Ghiberto/tap/embedinator` | Direct download |
| Windows (amd64) | `irm .../install.ps1 \| iex` | Scoop (future) | Direct download |
| Windows (arm64) | `irm .../install.ps1 \| iex` | Scoop (future) | Direct download |
| Any (Go developer) | `go install github.com/Bruno-Ghiberto/The-Embedinator/cli@latest` | - | - |

### 4.3 End-to-End User Experience

**First-time user on macOS:**

```
# Step 1: Install the CLI (one-time, 10 seconds)
$ brew install Bruno-Ghiberto/tap/embedinator

# Step 2: Navigate to where they want the project
$ cd ~/projects
$ git clone https://github.com/Bruno-Ghiberto/The-Embedinator.git
$ cd The-Embedinator

# Step 3: Run the single command
$ embedinator

# What happens:
#   - No config.yaml detected -> launches TUI wizard
#   - Welcome screen with ASCII gorilla art
#   - Preflight checks (Docker running? Enough disk? Enough RAM?)
#   - Ollama configuration (detects local Ollama if present)
#   - Port configuration (checks for conflicts, lets user choose)
#   - GPU detection (NVIDIA/AMD/Intel chain diagnosis)
#   - Model selection (qwen2.5:7b + nomic-embed-text defaults)
#   - Optional API key configuration
#   - Summary and confirmation
#   - Installation progress (docker compose up, health checks, model pulls)
#   - Completion screen with URLs and next steps
#
# Total time: 5-15 minutes (depending on download speed)

# Step 4: Open browser (from the TUI or manually)
# http://localhost:3000 -> The Embedinator UI

# Every subsequent run:
$ embedinator        # Starts services if stopped, shows status if running
$ embedinator stop   # Stops everything
$ embedinator doctor # Troubleshooting
```

**First-time user on Linux:**

```
# Step 1: Install the CLI
$ curl -fsSL https://raw.githubusercontent.com/Bruno-Ghiberto/The-Embedinator/main/cli/scripts/install.sh | bash

# Output:
# [embedinator] Installing The Embedinator CLI...
# [embedinator] Detected platform: linux/amd64
# [embedinator] Checking latest release...
# [embedinator] Latest version: v0.3.0
# [embedinator] Downloading embedinator_v0.3.0_linux_amd64.tar.gz...
# [embedinator] Downloading checksums...
# [embedinator] Verifying checksum...
# [embedinator] Checksum verified.
# [embedinator] Extracting binary...
# [embedinator] Installing to /usr/local/bin/embedinator...
# [embedinator] The Embedinator CLI v0.3.0 installed successfully!

# Step 2: Same as macOS from here
$ cd ~/projects && git clone ... && cd The-Embedinator
$ embedinator
```

**First-time user on Windows:**

```powershell
# Step 1: Install the CLI (PowerShell as regular user -- no admin needed)
PS> irm https://raw.githubusercontent.com/Bruno-Ghiberto/The-Embedinator/main/cli/scripts/install.ps1 | iex

# Output:
# [embedinator] Installing The Embedinator CLI...
# [embedinator] Detected platform: windows/amd64
# [embedinator] Latest version: v0.3.0
# [embedinator] Downloading embedinator_v0.3.0_windows_amd64.zip...
# [embedinator] Checksum verified.
# [embedinator] Installing to C:\Users\<user>\AppData\Local\Programs\embedinator...
# [embedinator] Adding to user PATH...
# [embedinator] The Embedinator CLI v0.3.0 installed successfully!
#
# IMPORTANT: Open a new terminal window for PATH changes to take effect.

# Step 2: Open new terminal, then same flow
PS> cd C:\projects
PS> git clone ... ; cd The-Embedinator
PS> embedinator
```

### 4.4 How GoReleaser Ties It Together

The release pipeline is:

```
Developer pushes tag: git tag cli/v0.3.0 && git push --tags
                              |
                              v
          GitHub Actions: .github/workflows/release-cli.yml
                              |
                              v
                     goreleaser release --clean
                              |
           +------------------+------------------+
           |                  |                  |
           v                  v                  v
     Build 6 binaries   Create Archives   Generate Checksums
     (CGO_ENABLED=0)    (tar.gz + zip)    (checksums.txt SHA-256)
           |                  |                  |
           +------------------+------------------+
                              |
           +------------------+------------------+
           |                  |                  |
           v                  v                  v
     GitHub Release      Homebrew Tap       Install Scripts
     (6 archives +       (auto-push to      (attached as
      checksums +         homebrew-tap       extra_files on
      install scripts)    repo Formula/)     the Release)
```

Each distribution channel reads from the same set of artifacts:

- **Homebrew:** goreleaser pushes the formula to `Bruno-Ghiberto/homebrew-tap`. The formula includes SHA-256 hashes for each archive and platform-specific download URLs.
- **curl|sh:** The install.sh script queries the GitHub Releases API for the latest `cli/v*` tag, downloads the correct archive, verifies SHA-256, extracts, and installs.
- **irm|iex:** Same as curl|sh but for PowerShell on Windows.
- **go install:** Builds from source using the Go toolchain. Does not use goreleaser artifacts.
- **Direct download:** User manually downloads from the GitHub Releases page.

### 4.5 URL Scheme

| Purpose | URL |
|---------|-----|
| Install script (bash) | `https://raw.githubusercontent.com/Bruno-Ghiberto/The-Embedinator/main/cli/scripts/install.sh` |
| Install script (PS) | `https://raw.githubusercontent.com/Bruno-Ghiberto/The-Embedinator/main/cli/scripts/install.ps1` |
| GitHub Releases | `https://github.com/Bruno-Ghiberto/The-Embedinator/releases` |
| Homebrew tap | `https://github.com/Bruno-Ghiberto/homebrew-tap` |
| Go install | `github.com/Bruno-Ghiberto/The-Embedinator/cli@latest` |

**Future consideration:** When the project gets a custom domain (e.g., `embedinator.dev`), the install URLs can be shortened:
- `curl -fsSL https://embedinator.dev/install.sh | bash`
- `irm https://embedinator.dev/install.ps1 | iex`

This requires hosting the scripts on GitHub Pages or a CDN with redirect, but is purely cosmetic and not blocking.

### 4.6 Package Manager Strategy (Future)

Beyond the v1 distribution channels:

| Channel | Effort | Benefit | Priority |
|---------|--------|---------|----------|
| **Scoop** (Windows) | Low -- add a scoop manifest JSON to a scoop bucket repo | Windows users who prefer Scoop over PowerShell one-liners | Post-v1 |
| **Chocolatey** (Windows) | Medium -- requires review process and .nuspec packaging | Enterprise Windows environments | Post-v1 |
| **apt/dnf repos** | High -- requires hosting a package repo with GPG signing | Linux users who prefer native package managers | Post-v1 |
| **AUR** (Arch) | Low -- PKGBUILD file in AUR | Arch Linux users | Post-v1 |
| **Nix** | Medium -- nixpkg expression | Nix/NixOS users | Post-v1 |
| **Docker image** | Low -- `FROM scratch` + binary | CI/CD and container-native users | Not recommended (the binary manages Docker -- running it inside Docker creates nesting) |

The goreleaser Homebrew tap is the highest-leverage secondary channel because it serves both macOS and Linux with zero additional infrastructure.

### 4.7 `go install` Path Correction

The design doc (section 3.4) notes that `go install` produces a binary named `cli` (the module directory name). The proposed fix is to move the entry point to `cli/cmd/embedinator/main.go` so that `go install github.com/Bruno-Ghiberto/The-Embedinator/cli/cmd/embedinator@latest` produces a binary named `embedinator`.

Current state: main.go is at `cli/main.go`, so `go install` would produce a binary named `cli`. This should be addressed before release, though it only affects Go developers who install from source.

### 4.8 Prerequisites Before First Release

Before running `goreleaser release --clean` for the first time:

1. **Create `Bruno-Ghiberto/homebrew-tap` repository** on GitHub. Must be public. Empty repo is fine -- goreleaser will push the Formula/ directory.

2. **Create `HOMEBREW_TAP_TOKEN` secret** in the `The-Embedinator` repository settings. This should be a GitHub personal access token with `repo` scope on the `homebrew-tap` repository.

3. **Create `.github/workflows/release-cli.yml`** in the main repository. The design doc provides the exact content (section 8.2).

4. **Create `.github/workflows/ci-cli.yml`** for PR/push CI on the `cli/` path.

5. **Tag the first CLI release:** `git tag cli/v0.1.0` (or whatever the initial version is).

---

## 5. Recommendations

### Priority 1: Critical (Must Fix Before Any Release)

**R1. Implement interactive port selection (Section 2)**

Replace `autoResolveConflicts()` in `wizard/ports.go` with the three-phase approach: scan, resolve (with user choice per conflict), review. This is the user's stated requirement and the single most important UX gap.

Estimated effort: Moderate. The engine layer (`engine/ports.go`) already has `FindAvailablePort()` and `ValidatePort()`. The work is in the wizard layer -- replacing the auto-resolve logic with huh.Select and huh.Input forms per conflict.

**R2. Fix self-update archive extraction**

`engine/selfupdate.go` DownloadUpdate() returns the path to a .tar.gz/.zip archive. ApplySelfUpdate() must extract the binary from the archive before renaming. Without this fix, `embedinator update` corrupts the installation.

Estimated effort: Small. Add a `extractBinary(archivePath, tmpDir string) (string, error)` function that handles tar.gz (Linux/macOS) and zip (Windows) extraction.

**R3. Create GitHub Actions workflows**

Both `release-cli.yml` and `ci-cli.yml` are required for distribution. Without the release workflow, goreleaser cannot run. Without CI, there is no automated testing.

Estimated effort: Small. The design doc provides the exact YAML content.

**R4. Create the Homebrew tap repository**

A public repository at `Bruno-Ghiberto/homebrew-tap` must exist before the first goreleaser release.

Estimated effort: Minimal. `gh repo create Bruno-Ghiberto/homebrew-tap --public`.

### Priority 2: Important (Should Fix Before Public Release)

**R5. Implement non-interactive setup mode**

`cmd/setup.go` currently runs the wizard in both interactive and non-interactive paths. The non-interactive path should: load defaults (or config.yaml), validate, generate .env, write config, compose up, poll health, pull models -- all without any TUI screens.

Estimated effort: Moderate. The engine layer has all the functions. The work is wiring them in a sequential, non-TUI codepath.

**R6. Implement API key input**

`wizard/apikeys.go` captures provider selection but never collects the actual key. Add a huh.Input with EchoMode(huh.EchoModePassword) for each selected provider. Validate key format (sk- prefix for OpenAI, etc.).

Estimated effort: Small. One huh.Input form per selected provider.

**R7. Implement remote Ollama URL input**

`wizard/ollama.go` hardcodes `http://localhost:11434` when remote mode is selected. Add a huh.Input with URL validation (scheme, host, port) and an optional reachability check.

Estimated effort: Small. One huh.Input with a validation function.

**R8. Implement Fernet key generation**

The WizardState has a `FernetKey` field but nothing populates it. The progress screen writes it to .env, but if it is empty, the backend will fail to start. Either generate a Fernet key natively in Go (using `crypto/rand` to generate 32 bytes, base64-encode) or shell out to `docker run python:3.14-slim -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

Estimated effort: Small for Go-native approach (preferred). The Fernet key format is `base64(random_16_bytes) + base64(random_16_bytes)` URL-safe base64 encoded. This can be done with stdlib `crypto/rand` and `encoding/base64`.

### Priority 3: Desirable (Post-Launch)

**R9. Add engine unit tests**

The design doc lists `_test.go` files for every engine package. These are absent. Priority areas: config R/W, port scanning, .env generation, overlay generation. GPU detection and Docker operations are harder to test without mocks but should have at least happy-path tests.

**R10. Add `-UseBasicParsing` fix to install.ps1**

Remove `-UseBasicParsing` from the `Invoke-RestMethod` call on line 66. It is an `Invoke-WebRequest` flag and is silently ignored on `Invoke-RestMethod`. Not a functional issue but should be cleaned up.

**R11. Improve GitHub API JSON parsing in install.sh**

Replace the grep/sed JSON parsing with `jq` when available, falling back to the current approach. This is more robust against API format changes.

**R12. Move main.go for go install naming**

Move `cli/main.go` to `cli/cmd/embedinator/main.go` so that `go install` produces a binary named `embedinator` instead of `cli`. Update goreleaser's `main:` path accordingly.

**R13. Migrate from docker CLI exec to Docker SDK**

Replace `os/exec` Docker calls with the `docker/docker` client library for structured output, streaming events, and elimination of subprocess overhead. This is a significant refactor but improves reliability and enables features like real-time build progress in the TUI.

---

## 6. Architecture Diagram

### 6.1 Distribution Pipeline

```
                           Developer
                              |
                        git tag cli/v0.3.0
                        git push --tags
                              |
                              v
                  +---------------------------+
                  |    GitHub Actions CI/CD    |
                  |  .github/workflows/       |
                  |  release-cli.yml          |
                  +---------------------------+
                              |
                              v
                  +---------------------------+
                  |      goreleaser v2         |
                  |  (runs inside CLI dir)     |
                  +---------------------------+
                    |         |          |
         +----------+    +---+---+    +--+----------+
         |               |           |              |
         v               v           v              v
   +----------+   +-----------+  +---------+  +----------+
   | 6 Binary |   | checksums |  | Homebrew|  | Release  |
   | Archives |   | .txt      |  | Formula |  | Assets   |
   | tar.gz   |   | (SHA-256) |  | .rb     |  | + Scripts|
   | + .zip   |   |           |  |         |  |          |
   +----------+   +-----------+  +---------+  +----------+
         |               |           |              |
         +-------+-------+           |              |
                 |                    |              |
                 v                    v              v
   +---------------------------+  +--------+  +-----------+
   | GitHub Release Page       |  | Bruno- |  | raw.git   |
   | Bruno-Ghiberto/           |  | Ghib/  |  | hubuser   |
   |   The-Embedinator         |  | homebr |  | content   |
   |   /releases/cli/v0.3.0   |  | ew-tap |  | .com/...  |
   +---------------------------+  +--------+  +-----------+
         |         |                  |              |
         |         |                  |              |
   +-----+---------+-----+    +------+-------+------+-----+
   |     |         |     |    |              |             |
   v     v         v     v    v              v             v
 +---+ +---+   +-----+  +--------+  +----------+  +----------+
 |Lin| |mac|   |Win  |  |Homebrew|  |curl|bash |  |irm |iex  |
 |ux | |OS |   |     |  |brew    |  |install.sh|  |install.ps1|
 |dl | |dl |   |dl   |  |install |  |Linux/mac |  |Windows    |
 +---+ +---+   +-----+  +--------+  +----------+  +----------+
   |     |         |          |            |              |
   +-----+---------+----------+------------+--------------+
                              |
                              v
                  +---------------------------+
                  |   embedinator binary      |
                  |   (on user's machine)     |
                  +---------------------------+
                              |
                         user runs:
                        $ embedinator
                              |
                    +---------+---------+
                    |                   |
                    v                   v
           +---------------+   +---------------+
           | First run:    |   | Subsequent:   |
           | TUI Wizard    |   | Start/Status  |
           | (10 screens)  |   | (non-TUI)     |
           +---------------+   +---------------+
                    |
                    v
           +---------------+
           | Docker Compose|
           | Stack Running |
           | (4 services)  |
           +---------------+
```

### 6.2 CLI Internal Architecture

```
+---------------------------------------------------------------------+
|  embedinator binary                                                  |
|                                                                      |
|  cmd/ (Cobra Layer)                                                  |
|  +-------+-------+-------+--------+-------+------+------+--------+ |
|  | root  | setup | start | stop   | status| logs | cfg  | doctor | |
|  | (smart| (TUI  | (non  | (non   | (JSON | (pass| (TUI | (diag  | |
|  |  dflt)| wiz)  | -TUI) | -TUI)  | +tbl) | thru)| wiz) | report)| |
|  +---+---+---+---+---+---+---+----+---+---+--+---+--+---+---+----+ |
|      |       |       |       |         |      |      |       |      |
|      v       v       |       |         v      v      v       v      |
|  wizard/ (Bubbletea TUI Layer)    engine/ (Pure Logic Layer)        |
|  +---------------------------+    +--------------------------------+|
|  | WizardModel (orchestrator)|    | config.go   - YAML R/W        ||
|  |   |                      |    | docker.go   - Compose ops      ||
|  |   +-> WelcomeModel       |    | dotenv.go   - .env generation  ||
|  |   +-> PrerequisitesModel  |    | gpu.go      - GPU diagnostics  ||
|  |   +-> OllamaModel        |    | ollama.go   - Ollama detection ||
|  |   +-> PortsModel  <------+--->| ports.go    - Port scanning    ||
|  |   +-> GPUModel            |    | preflight.go- System checks    ||
|  |   +-> ModelsModel         |    | overlay.go  - Compose overlays ||
|  |   +-> APIKeysModel        |    | selfupdate.go - Binary update  ||
|  |   +-> SummaryModel        |    | sysinfo.go  - OS/arch detect   ||
|  |   +-> ProgressModel  ----+--->| (all funcs) - Used by progress ||
|  |   +-> CompleteModel       |    +--------------------------------+|
|  |                           |                                      |
|  | state.go (WizardState)    |    version/                          |
|  | styles.go (lipgloss)      |    +--------------------------------+|
|  +---------------------------+    | version.go  - Build-time vars  ||
|                                   +--------------------------------+|
+---------------------------------------------------------------------+
                    |
                    | os/exec (docker CLI)
                    v
+---------------------------------------------------------------------+
| Docker Compose Stack                                                 |
| +----------+ +----------+ +-----------+ +-----------+               |
| | qdrant   | | ollama   | | backend   | | frontend  |               |
| | :6333    | | :11434   | | :8000     | | :3000     |               |
| +----------+ +----------+ +-----------+ +-----------+               |
+---------------------------------------------------------------------+
```

### 6.3 Port Selection State Machine

```
                    Init()
                      |
                      v
              +---------------+
              |   Scanning    |  <-- engine.CheckAllPorts()
              | (portPhase=0) |
              +-------+-------+
                      |
              portScanDoneMsg
                      |
            +---------+---------+
            |                   |
     All ports clear     Conflicts found
            |                   |
            v                   v
     +-------------+   +---------------+
     |   Review    |   |   Resolving   |  <-- huh.Select per conflict
     | (portPhase  |   | (portPhase=1) |
     |   =3)       |   +-------+-------+
     +------+------+           |
            |           +------+------+------+
            |           |             |      |
            |     "suggested"   "custom" "keep"
            |           |             |      |
            |           v             v      v
            |     Apply auto-   +--------+  Warn user,
            |     suggested     | Custom |  leave as-is
            |     port          | Input  |
            |           |       | (phase |
            |           |       |   =2)  |
            |           |       +---+----+
            |           |           |
            |           |     Validate + apply
            |           |           |
            |           +-----+-----+
            |                 |
            |           Next conflict?
            |           +-----+-----+
            |           |           |
            |          Yes          No
            |           |           |
            |           v           v
            |   (back to      +-------------+
            |    Resolving)   |   Review    |
            |                 | (portPhase  |
            |                 |   =3)       |
            |                 +------+------+
            |                        |
            +--------+---------------+
                     |
                Enter pressed
                     |
                     v
              NextScreenMsg
```

---

## Appendix: File Inventory

All files analyzed in the `cli/` directory:

```
cli/
  go.mod                                    (42 lines)
  go.sum                                    (91 lines)
  main.go                                   (13 lines)
  .goreleaser.yml                           (125 lines)
  cmd/
    root.go                                 (97 lines)
    setup.go                                (41 lines)
    start.go                                (98 lines)
    stop.go                                 (49 lines)
    restart.go                              (31 lines)
    status.go                               (101 lines)
    logs.go                                 (50 lines)
    config_cmd.go                           (52 lines)
    doctor.go                               (180 lines)
    version_cmd.go                          (22 lines)
    completion.go                           (55 lines)
    update.go                               (102 lines)
  internal/
    version/
      version.go                            (15 lines)
    engine/
      config.go                             (181 lines)
      docker.go                             (241 lines)
      dotenv.go                             (160 lines)
      gpu.go                                (867 lines)
      ollama.go                             (159 lines)
      overlay.go                            (160 lines)
      ports.go                              (108 lines)
      preflight.go                          (350 lines)
      selfupdate.go                         (111 lines)
      sysinfo.go                            (90 lines)
    wizard/
      wizard.go                             (131 lines)
      state.go                              (104 lines)
      styles.go                             (125 lines)
      welcome.go                            (91 lines)
      prerequisites.go                      (120 lines)
      ollama.go                             (131 lines)
      ports.go                              (167 lines)
      gpu.go                                (479 lines)
      models.go                             (128 lines)
      apikeys.go                            (98 lines)
      summary.go                            (122 lines)
      progress.go                           (271 lines)
      complete.go                           (92 lines)
  scripts/
    install.sh                              (306 lines)
    install.ps1                             (274 lines)

Total: 37 Go source files + 2 scripts + 1 goreleaser config
Approximate total Go LOC: ~4,900
```
