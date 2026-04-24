# Research: E2E Bug Hunt & Quality Baseline — Phase 0 Output

**Feature**: spec-28
**Date**: 2026-04-23

This document resolves the unknowns surfaced by the Technical Context of `plan.md`. Each section records a single decision plus rationale and rejected alternatives.

---

## 1. RAGAS API surface for Spanish-language evaluation

**Decision**: Use the `ragas` Python library with four metrics from `ragas.metrics`: `context_precision`, `context_recall`, `answer_relevancy`, `faithfulness`. Wrap backend responses in a `ragas.Dataset` (`question`, `answer`, `contexts`, `reference`) per pair; run `ragas.evaluate()` once over all 20 entries; collect per-metric scores and write them to `quality-metrics.md`.

**Rationale**:
- These four metrics map 1:1 to FR-016 (retrieval precision, answer relevance, citation faithfulness, context recall).
- `ragas` is language-agnostic; it calls whatever LLM is configured via its `llm` setting to judge relevance. For Spanish, we either use the same local Ollama model the backend uses (consistent, risks self-referential bias) or a cloud judge via opt-in API key (more neutral, adds a provider dependency).
- Library defaults are well-documented; no custom scoring code means lower bug surface in our own harness.

**Spanish-specific notes**:
- RAGAS does not transliterate or translate; it runs the judge LLM on the provided text in its native language.
- If `ragas.evaluate()` returns `nan` for any pair (typically a retrieval-empty case on out-of-scope questions), treat as `N/A (declined)` in the report per the quality-metrics.md layout — do not zero-fill.

**Judge LLM choice — deferred to plan's open question #2**:
- The plan flagged "scaffold mechanics for the 17 easier Q&A pairs" as open. The same decision applies to the RAGAS judge: if the judge is the backend's own model, baseline scores are inflated by self-agreement; if the judge is a separate cloud model, the user must consent to the one-time API call.
- **Recommendation for `/speckit.tasks`**: use the local Ollama judge for the baseline (consistency with the local-first principle), document the self-bias risk in quality-metrics.md's "Reproduction" section, and make "run with cloud judge" a reproducible `pytest --judge=openrouter` follow-up the user can opt into.

**Alternatives considered**:
- **Hand-roll via sentence-transformers similarity**: rejected per spec Assumptions and plan Complexity Tracking. More custom code, no measurement validation history.
- **promptfoo or TruLens**: rejected. Adds a second measurement library for the same four metrics RAGAS covers, doubles the dependency surface.
- **No quality measurement at all**: rejected. SC-003 is explicit; portfolio value depends on defensible numbers.

**References**:
- `ragas` documentation: `https://docs.ragas.io/` — check version compatibility with LangChain 1.2.10 at pin time.
- Community Spanish-on-English-embedder benchmarks suggest 15–30 % retrieval precision degradation relative to English corpora with the same embedder. This forms the quantitative backstop for hypothesis H1 in `quality-metrics.md`.

---

## 2. Playwright strict-mode selector migration

**Decision**: Migrate all `getByText` selectors that match text appearing in `sr-only` accessibility spans to either `getByRole("<role>", { name: /.../, exact: true })` or to `getByText(..., { exact: true })` combined with a scope locator (`within(card)`). The canonical root cause pattern is the spec-22 dropdown button emitting `<span class="sr-only">Actions for {name}</span>` alongside the visible card title `<h3>{name}</h3>`.

**Rationale**:
- `getByText` in Playwright v1.50 uses strict mode by default: it throws if the locator resolves to more than one element. The sr-only accessibility spans are real DOM nodes and are indistinguishable from the visible text by `getByText` alone.
- `getByRole` is the Playwright-recommended API for this case because it targets the semantic role (heading, button, listitem), cannot match plain text spans, and is stable across visual restyles.
- `exact: true` plus a scope narrow is acceptable where no meaningful role exists (e.g., plain div content).

**Concrete migration examples**:

| Current (failing) | Migrated |
|-------------------|----------|
| `page.getByText("e2e-workflow-abc")` | `page.getByRole("heading", { name: "e2e-workflow-abc", exact: true })` |
| `page.getByText("Delete")` | `page.getByRole("button", { name: "Delete", exact: true })` |
| `page.getByText("Settings saved")` | `page.locator('[role=status]').getByText("Settings saved", { exact: true })` |

**Alternatives considered**:
- **Remove the `sr-only` accessibility spans from spec-22's dropdown**: rejected. The spans are a legitimate accessibility affordance (screen-reader action announcement); removing them would regress accessibility. Fix the tests, not the app.
- **Disable strict mode globally**: rejected. Strict mode catches exactly this class of test-drift; disabling would re-open the four-week silent-drift problem spec-28 is chartered to close.
- **Use `.first()` everywhere**: rejected. `.first()` silently accepts the wrong element if the accessibility span happens to precede the visible title in the DOM.

**References**:
- Playwright v1.50 locator strict-mode docs: `https://playwright.dev/docs/locators#strictness`
- Spec-22 implementation-complete engram — sidebar dropdown introduced the `sr-only` scaffolding.

---

## 3. GitHub Actions `actions/upload-artifact@v7` path resolution

**Decision**: Use an explicit absolute-style path from the repository root: `frontend/playwright-report/` (with trailing slash). If the Playwright config writes its report to a different path, either reconcile the config to emit to `playwright-report/` (the Playwright default) or update the CI step's `path:` key to the config's `reporter[0].outputFolder` value.

**Rationale**:
- The 2026-04-22 CI run produced "No files were found with the provided path: frontend/playwright-report/". Root cause options:
  1. The Playwright `frontend-e2e` job is running `npm run e2e` in the repo root (not `cd frontend`) and Playwright writes `playwright-report/` at the root level — the upload step is looking in `frontend/playwright-report/` which doesn't exist.
  2. The Playwright config overrides `outputFolder` to something else (e.g., `reports/html/`) and the upload step is pointing at the default location.
  3. The job's working directory is correct but the Playwright run crashed before writing any report (suite never produced output).
- The fix requires reading `frontend/playwright.config.ts` and the `_ci-core.yml` workflow to identify which of the three applies. It is NOT a library bug in `actions/upload-artifact@v7`.

**Action for Phase 1 Test Runner pane**:
1. Read `frontend/playwright.config.ts` to locate the `reporter` configuration and its `outputFolder`.
2. Read the `frontend-e2e` job's `run:` step to confirm the working directory.
3. Align the three paths (Playwright reporter output, CI working directory, upload-artifact `path:`).
4. Set `if: always()` on the upload step so trace artifacts are uploaded even on test failure (they're more useful when tests fail).

**Alternatives considered**:
- **Downgrade `upload-artifact` to v6**: rejected. v7 is the current standard; the path-resolution behavior is the same. Downgrading just kicks the can.
- **Add `allowMissing: true`**: rejected. Masks the bug. The point is to have traces when tests fail.

**References**:
- `actions/upload-artifact@v7` README: `https://github.com/actions/upload-artifact` — note the `path:` input is resolved relative to `$GITHUB_WORKSPACE`.

---

## 4. Tmux 4-pane Claude session setup

**Decision**: Document a concrete tmux spawn pattern in `quickstart.md`. User runs `tmux new-session -s spec28` then splits into 4 panes (2×2 grid). In each pane, user invokes `claude` with an explicit model flag and an MCP allowlist corresponding to the pane's role (Orchestrator = Opus + sequential-thinking / engram / serena / gitnexus; Test Runner = Sonnet + playwright / chrome-devtools / docker; Scribe = Sonnet + rust-mcp-filesystem / gitnexus / serena; Log Watcher = Sonnet + docker / rust-mcp-filesystem / browser-tools).

**Rationale**:
- Each pane needs its own Claude session with its own context window. Running them in separate tmux panes (one Claude process per pane) is the canonical pattern the user has used for prior specs (26, 27).
- Model differentiation (Opus vs Sonnet) matters: orchestration decisions benefit from Opus's reasoning; scribe/log-watching is routine and Sonnet-efficient.
- MCP allocation per pane prevents tool sprawl and keeps each session's context budget focused.

**Documented spawn commands** (see quickstart.md for the full reference):
```bash
tmux new-session -s spec28 \; \
  split-window -h \; \
  split-window -v \; \
  select-pane -t 0 \; \
  split-window -v
```
Then in each pane:
```bash
# Pane 1 (Orchestrator, Opus)
claude --model claude-opus-4-7

# Pane 2 (Test Runner, Sonnet)
claude --model claude-sonnet-4-6

# Pane 3 (Scribe, Sonnet)
claude --model claude-sonnet-4-6

# Pane 4 (Log Watcher, Sonnet)
claude --model claude-sonnet-4-6
```

MCP restriction per pane is enforced by the user choosing which MCPs to enable via `claude mcp` management per session. The plan does not automate this — it is a session-discipline contract.

**Alternatives considered**:
- **Use Agent Teams Lite with TeamCreate/Agent**: rejected per plan enforcement banner. F/D/P gates are synchronous; async wave spawning cannot serve a human-in-the-loop session.
- **Single-Claude with Bash/screen backgrounding**: rejected. Tool context pollutes a single conversation; F/D/P prompts would be drowned by log-watching output.
- **Zellij instead of tmux**: rejected for consistency with prior specs and the user's setup docs (`Docs/Setups/tmux.md`).

**References**:
- `Docs/Setups/tmux.md` (existing, user's tmux setup reference)
- Prior session engram: Agent Teams `tmux multi-pane is MANDATORY when using Agent Teams` — here we apply the inverse: same tmux discipline, but manual pane spawning.

---

## 5. Fault-injection Docker commands — validation against the real stack

**Decision**: Validate against `docker compose ps --format json` at session start to confirm container names match the catalog in `plan.md` §"Fault Injection Scenarios". Expected container names (from `docker-compose.yml` service keys + project prefix):

| Service | Expected container name |
|---------|-------------------------|
| ollama | `embedinator-ollama-1` |
| qdrant | `embedinator-qdrant-1` |
| backend | `embedinator-backend-1` |
| frontend | `embedinator-frontend-1` |

**Rationale**:
- Docker Compose v2 generates container names as `{project}-{service}-{replica}` by default. The project name defaults to the directory name (`embedinator` if launched from repo root) or can be set by `COMPOSE_PROJECT_NAME`.
- The existing launcher scripts (`embedinator.sh`) do not set `COMPOSE_PROJECT_NAME`, so the default applies.
- If the user is running from a different working directory or has a stale compose project with a different name, the fault commands will no-op silently. The Phase 4 preflight explicitly confirms names before issuing any fault command.

**Action for Phase 4 Test Runner pane**:
```bash
# Preflight — log actual container names
docker compose ps --format json | jq -r '.[] | .Name'
# Expected output:
# embedinator-ollama-1
# embedinator-qdrant-1
# embedinator-backend-1
# embedinator-frontend-1
```

If the names differ, update the scenario catalog's fault commands inline before issuing them.

**Observed behavior expectations**:
- **FI-01 Ollama kill**: The backend's tenacity-based retry + circuit breaker (per spec-13 / ADR) trips after 3 attempts; user sees a graceful error in the chat UI. If the user sees a 502/504 with no error framing, that's a Blocker.
- **FI-02 Qdrant stop**: The retrieval layer's circuit breaker trips; user sees "retrieval unavailable" UI state. If the UI silently returns an empty result set, that's a Blocker.
- **FI-03 Backend crash mid-stream**: NDJSON stream terminates; frontend's stream-handling must surface a disconnect indicator. If the UI spins forever, that's a Blocker.
- **FI-04 Network partition**: The backend's Ollama client times out; same error framing expected as FI-01.
- **FI-05 Context-length exceeded**: The backend must return a 400 with a clear size-limit message or truncate-and-warn. A 500 with a stack trace is a Blocker.

**Alternatives considered**:
- **Use a chaos-engineering tool (chaos-mesh, chaosblade, toxiproxy)**: rejected per spec Non-Goals. Adds a fifth Docker service (violates Constitution VII). Plain `docker` CLI is sufficient for 5 scenarios.
- **Mock the fault via backend middleware**: rejected. Mocks bypass the real container / network / process kill behavior that is exactly what's under test.

**References**:
- `docker-compose.yml` (repo root)
- `backend/errors.py` custom exception hierarchy — these are the error shapes the UI should render
- Spec-13 security, Spec-15 observability — fault-injection traces must not leak credentials

---

## Summary

| Unknown | Resolution |
|---------|-----------|
| RAGAS API + metrics choice | 4 metrics from `ragas.metrics`; Spanish-native judge (local Ollama default; cloud-judge opt-in follow-up) |
| Playwright strict-mode migration | `getByRole` / `{exact: true}` + scope; don't remove `sr-only` spans |
| upload-artifact path void | Reconcile Playwright reporter outputFolder ↔ CI workdir ↔ upload step path; `if: always()` |
| tmux 4-pane setup | Documented spawn commands in quickstart.md; per-pane model + MCP allowlist |
| Fault-injection commands | `docker compose ps` preflight confirms names; scenario catalog validated against stack |

Zero `[NEEDS CLARIFICATION]` items remain. Ready for Phase 1 Design & Contracts.
