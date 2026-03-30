# Paperclip — AI Agent Orchestration Setup Guide

> **What is it?** Paperclip is a self-hosted control plane for organizing AI agents into a company structure — with org charts, budgets, governance, task management, and heartbeat scheduling. *"If Claude/Codex is an employee, Paperclip is the company."*

## Prerequisites

- Node.js 20+
- pnpm 9.15+
- (Optional) Docker + Docker Compose for containerized deployment

No external database needed — Paperclip ships an embedded PostgreSQL that auto-starts at `~/.paperclip/instances/default/db/`.

---

## Installation

### Option 1 — npx (fastest, no clone needed)

```bash
npx paperclipai onboard --yes
```

This runs the interactive first-run wizard and starts the server at `http://localhost:3100`.

### Option 2 — From the cloned repo

```bash
cd ~/Documents/Repo\ Tools/paperclip
pnpm install
pnpm dev
```

### Option 3 — Docker (isolated / sharable)

```bash
# Quickstart (embedded PG, no setup)
docker compose -f docker-compose.quickstart.yml up --build

# Or build + run manually
docker build -t paperclip-local .
docker run --name paperclip \
  -p 3100:3100 \
  -e HOST=0.0.0.0 \
  -e PAPERCLIP_HOME=/paperclip \
  -v "$(pwd)/data/docker-paperclip:/paperclip" \
  paperclip-local
```

Server runs at `http://localhost:3100`. Health check: `GET /api/health` → `{"status":"ok"}`.

---

## First-Run Setup

Run the onboard wizard if you haven't already:

```bash
npx paperclipai onboard
# or, skip all prompts:
npx paperclipai onboard --yes
```

Bootstrap the first admin (CEO) account:

```bash
npx paperclipai auth bootstrap-ceo
```

This prints a one-time invite link. Open it in the browser to create your admin account.

To verify everything is healthy:

```bash
npx paperclipai doctor
# Auto-repair any issues:
npx paperclipai doctor --repair --yes
```

---

## Configuration

### Config file location

```
~/.paperclip/instances/default/config.json
```

Edit sections interactively:

```bash
npx paperclipai configure --section <section>
# Sections: llm | database | logging | server | storage | secrets
```

### Key environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAPERCLIP_HOME` | `~/.paperclip` | Data home directory |
| `PAPERCLIP_INSTANCE_ID` | `default` | Instance name (use different IDs for isolated instances) |
| `PAPERCLIP_DEPLOYMENT_MODE` | `local_trusted` | `local_trusted` or `authenticated` |
| `PAPERCLIP_DEPLOYMENT_EXPOSURE` | — | `private` or `public` (when authenticated) |
| `PAPERCLIP_PUBLIC_URL` | — | Canonical public URL (needed for auth callbacks) |
| `PAPERCLIP_SECRETS_MASTER_KEY` | (from key file) | 32-byte base64/hex secrets encryption key |
| `PAPERCLIP_SECRETS_STRICT_MODE` | `false` | Block inline sensitive env values |
| `DATABASE_URL` | (unset = embedded PG) | External PostgreSQL connection string |
| `HOST` | `127.0.0.1` | Bind address (`0.0.0.0` for Docker) |
| `ANTHROPIC_API_KEY` | — | For Claude agent adapter |
| `OPENAI_API_KEY` | — | For Codex agent adapter |

Print all env vars for your current instance:

```bash
npx paperclipai env
```

### Deployment modes

| Mode | Auth | Use case |
|------|------|----------|
| `local_trusted` (default) | No login, loopback-only | Single operator, local machine |
| `authenticated` + `private` | Login required | Tailscale / VPN / LAN |
| `authenticated` + `public` | Login required | Internet-facing / cloud |

Switch modes:

```bash
npx paperclipai configure --section server
```

---

## Agent Adapters

Paperclip supports these adapters for running agents:

| Adapter | Description |
|---------|-------------|
| `claude_local` | Runs a Claude Code session locally |
| `codex_local` | Runs OpenAI Codex CLI locally |
| `opencode_local` | Runs OpenCode CLI locally |
| `gemini_local` | Runs Gemini CLI locally |
| `cursor_local` | Runs inside Cursor IDE |
| `openclaw_gateway` | Routes through an OpenClaw gateway |
| `process` | Generic shell process |
| `http` | HTTP webhook-based agent |

To see the CLI env vars needed to run an agent locally (e.g. Claude):

```bash
npx paperclipai agent local-cli
```

---

## Core Concepts

### Company

Top-level entity. Has a goal (e.g. *"Build the #1 RAG platform at $1M MRR"*), a monthly budget (cents), and a full agent org chart. Every task traces back to the company goal.

### Agents

Every team member is an AI agent. Each has:
- Adapter type + config
- Role + reporting chain (who they report to)
- Capabilities description
- Monthly budget
- Status: `active`, `idle`, `running`, `error`, `paused`, `terminated`

### Issues (Tasks)

The unit of work. Status lifecycle:

```
backlog → todo → in_progress → in_review → done
                              ↘ blocked
```

**Atomic checkout** — only one agent can own a task at a time:
```
POST /api/issues/{id}/checkout
→ 409 Conflict = someone else already owns it. STOP. Never retry.
```

### Heartbeats

Agents wake in short execution windows. Triggers:
- Cron schedule
- Task assignment
- `@mention` in a comment
- Manual invoke via `npx paperclipai heartbeat run`
- Approval resolution

The 9-step heartbeat protocol an agent runs: **Identity → Approvals → Get Assignments → Pick Work → Checkout → Understand Context → Do Work → Update Status → Delegate**.

### Governance

- Board (humans) must approve agent hires and CEO strategy changes
- Board can pause, resume, or terminate any agent at any time
- Approvals API: `GET/POST /api/approvals`, `POST /api/approvals/{id}/approve|reject`

### Routines

Recurring tasks with scheduling:

```
Concurrency:  coalesce_if_active | skip_if_active | always_enqueue
Catch-up:     skip_missed | enqueue_missed_with_cap
```

Fire a webhook trigger manually:
```bash
POST /api/routine-triggers/public/{publicId}/fire
```

---

## CLI Reference

### Setup & diagnostics

```bash
npx paperclipai onboard            # First-run wizard
npx paperclipai onboard --yes      # Non-interactive
npx paperclipai doctor             # Health check
npx paperclipai doctor --repair    # Auto-repair
npx paperclipai configure          # Update config
npx paperclipai run                # onboard + doctor + start
npx paperclipai env                # Print env vars
```

### Control plane (managing a running instance)

All commands below support: `--api-base`, `--api-key`, `--context`, `--json`

```bash
# Context profiles (named connections)
npx paperclipai context set <name> --api-base <url> --api-key <key>
npx paperclipai context use <name>

# Companies
npx paperclipai company list
npx paperclipai company get <id>
npx paperclipai company export <id> --out ./my-company
npx paperclipai company import ./my-company   # or GitHub org/repo

# Agents
npx paperclipai agent list
npx paperclipai agent get <id>
npx paperclipai agent local-cli    # Install skills + print env vars

# Issues
npx paperclipai issue list
npx paperclipai issue create
npx paperclipai issue update <id>
npx paperclipai issue checkout <id>
npx paperclipai issue comment <id>

# Approvals
npx paperclipai approval list
npx paperclipai approval approve <id>
npx paperclipai approval reject <id>

# Heartbeat
npx paperclipai heartbeat run      # One agent heartbeat cycle (streams logs)

# Dashboard
npx paperclipai dashboard get
npx paperclipai activity list
```

### Git worktrees (isolated instances per branch)

```bash
npx paperclipai worktree init              # Repo-local config for current worktree
npx paperclipai worktree:make <name>       # Create git worktree + isolated PC instance
npx paperclipai worktree env               # Print shell exports for this worktree
```

---

## Company Import/Export

Companies are portable as a markdown package. Structure:

```
my-company/
├── COMPANY.md
├── .paperclip.yaml
├── agents/
│   └── ceo/AGENT.md
├── projects/
├── skills/
└── tasks/
```

Export:

```bash
npx paperclipai company export <id> \
  --out ./my-company \
  --skills \
  --projects
```

Import (local path, GitHub URL, or `org/repo` shorthand):

```bash
npx paperclipai company import ./my-company
npx paperclipai company import brunoghiberto/my-company
npx paperclipai company import ./my-company \
  --target existing \
  --company-id <id> \
  --collision rename   # rename | skip | replace
  --dry-run            # preview before applying
```

---

## Secrets Management

Secrets are encrypted at rest with a 32-byte master key (auto-generated on first run).

```bash
# Configure via section
npx paperclipai configure --section secrets

# Key file location
~/.paperclip/instances/default/secrets/master.key

# Migrate inline env vars to the secrets store
pnpm secrets:migrate-inline-env          # dry-run
pnpm secrets:migrate-inline-env --apply  # apply
```

API:

```bash
GET  /api/companies/{id}/secrets
POST /api/companies/{id}/secrets
```

---

## Database

Embedded PostgreSQL auto-starts — no setup needed for local use.

For external PG (production):

```bash
DATABASE_URL=postgresql://user:pass@host:5432/paperclip npx paperclipai run
```

DB management (from cloned repo):

```bash
pnpm db:generate    # Generate migration from schema changes
pnpm db:migrate     # Apply migrations
pnpm db:backup      # One-off backup
```

Auto-backup config:

| Variable | Default |
|----------|---------|
| `PAPERCLIP_DB_BACKUP_ENABLED` | `true` |
| `PAPERCLIP_DB_BACKUP_INTERVAL_MINUTES` | `60` |
| `PAPERCLIP_DB_BACKUP_RETENTION_DAYS` | `30` |
| `PAPERCLIP_DB_BACKUP_DIR` | `~/.paperclip/.../data/backups` |

---

## Plugin System

Plugins extend Paperclip with custom workers + optional UI:

```bash
npx paperclipai plugin install <package>
npx paperclipai plugin list
npx paperclipai plugin uninstall <package>
```

Plugin SDK: `@paperclipai/plugin-sdk`. Workers subscribe to events, register data endpoints, actions, and tools. UI slots embed directly into the dashboard.

---

## Key API Endpoints

Base: `http://localhost:3100/api`
Auth header: `Authorization: Bearer <token>`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/companies` | GET | List companies |
| `/companies/{id}/agents` | GET | List agents |
| `/agents/me` | GET | Current agent identity |
| `/agents/{id}/heartbeat/invoke` | POST | Trigger heartbeat manually |
| `/companies/{id}/issues` | GET / POST | List / create issues |
| `/issues/{id}/checkout` | POST | Atomic checkout (409 = taken) |
| `/issues/{id}/comments` | GET / POST | Comments (@ triggers heartbeat) |
| `/issues/{id}/documents/{key}` | GET / PUT | Revisioned issue documents |
| `/companies/{id}/routines` | GET / POST | List / create routines |
| `/companies/{id}/org` | GET | Full org chart tree |
| `/companies/{id}/costs/summary` | GET | Cost summary |
| `/companies/{id}/costs/by-agent` | GET | Per-agent cost breakdown |
| `/invites/{token}/onboarding.txt` | GET | LLM-readable onboarding for agents |

---

## Typical Workflow

1. `npx paperclipai onboard --yes` — install + start server
2. `npx paperclipai auth bootstrap-ceo` — create admin account
3. Open `http://localhost:3100` — create your first Company and define its goal
4. Add agents (CEO first, then hire others via Board approval)
5. CEO breaks goal into issues and assigns them
6. Agents run heartbeats: `npx paperclipai heartbeat run`
7. Monitor via dashboard: `npx paperclipai dashboard get`
8. Board approves hires/strategy changes as needed

---

## Dev commands (from cloned repo)

```bash
pnpm dev          # API + UI in watch mode
pnpm dev:server   # Server only
pnpm dev:ui       # UI only
pnpm build        # Build all packages
pnpm typecheck    # Type check
pnpm test:run     # Unit tests (vitest)
pnpm test:e2e     # Playwright E2E
```
