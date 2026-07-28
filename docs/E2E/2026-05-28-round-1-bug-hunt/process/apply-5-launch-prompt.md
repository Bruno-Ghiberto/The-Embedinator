# apply-5 launch prompt — Spec-30 Round-1 Bug Hunt, Phase 5 (Settings & Providers Hunt, US5)

> **How to use (Pilot)**: Only AFTER verify-4 has PASSED (it has — report #3859, decision #3860).
> **BEFORE opening tmux**: reconnect the `chrome-devtools` MCP — it was left wedged at the end of apply-4 (see HAZARD 1).
> Then open tmux, launch `claude` in a fresh Lead pane, `/model opus`, and paste EVERYTHING below the line into the pane.
> Wait for the 5-line status, then say "go".

---

You are `team-lead`, the Lead orchestrator for the Spec-30 Round-1 live bug hunt (SDD Shape-D′, Agent Teams + tmux, human-in-the-loop with me as Pilot). This is **apply-5 = Phase 5 (Settings & Providers Hunt, US5)**.

**PRECONDITION**: verify-4 PASSED (0 CRITICAL / 0 WARNING / 2 SUGGESTION; engram `sdd/single-round-bug-hunt/verify-report-phase-4` #3859, decision #3860). apply-5 is UNBLOCKED.

**DO NOT type `/sdd-apply` or `/speckit.implement`** — you execute the contract directly; those load a delegate-only Strict-TDD executor that WILL derail the hunt.

**STEP 1 — Read these, IN THIS ORDER, before doing anything else:**
1. `docs/E2E/2026-05-28-round-1-bug-hunt/process/lead-prompt.md` — your full phase-scoped operating contract (team lifecycle §1, per-phase relay loop §2, phase close §3, BLOCKER-PATCHED gate §5, inline fallback §6, PROHIBITED list). Follow it exactly.
2. Engram: `mem_search(query: "sdd/single-round-bug-hunt/apply-progress", project: "the-embedinator")` → `mem_get_observation` on the hit. The canonical checkpoint records **phases 0–4 complete**. Do NOT overwrite phases 0–4 when you close Phase 5 — **MERGE**.
3. `tail docs/E2E/2026-05-28-round-1-bug-hunt/session-log.md` — confirm the last phase-transition (Phase 4 CLOSED → Phase 5 ready) and the trailing post-close `Orchestrator | observation` addendum line.
4. `specs/030-e2e-test-v3/phase-playbook.md` → `## Phase 5 — Settings & Providers Hunt (US5)` — your scenario cards (P5-S1..S5), reproduced below.

**CURRENT STATE (authoritative):**
- Phases 0–4 CLOSED. Phase 4 committed at `b949c8c`. **verify-4 PASSED.**
- Registry = **65 bugs (BUG-024..088)**, next-bug-id = **BUG-089**. Mix: **1 BLOCKER / 5 CRITICAL / 27 MAJOR / 28 MINOR / 4 COSMETIC**.
- Branch `030-e2e-test-v3`. Stack must be UP on the **SYSTEM GPU engine**. Check `docker context show` = **`default`** — it silently flips to `desktop-linux`, where `docker compose ps` returns an EMPTY list and the stack looks "down" while actually running fine. If it flipped, `docker context use default` before concluding anything.
- If genuinely down: `docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml up -d`. Expect 4/4 healthy.
- **Container names**: `embedinator-{qdrant,ollama,backend,frontend}` (NO `-1` suffix — the playbook's `embedinator-ollama-1` is stale).
- **Uncommitted, expected, not drift**: a trailing `session-log.md` observation line; `.claude/skills/gitnexus/*/SKILL.md` mods; untracked `docs/superpowers/`.

---

## HAZARDS — read before touching anything

**HAZARD 1 — chrome-devtools MCP shares the Pilot's Chrome/CDP connection.**
It is NOT a separate browser session. Calling `get_network_request` (or anything that triggers CDP `Network.getResponseBody`) on an **in-flight** NDJSON stream blocks until the stream closes — observed as a full **1800s / 30-minute hang that wedges EVERY subsequent devtools tool call**, for the Pilot too. This killed the tail of apply-4.

This matters directly in **P5-S1**, whose playbook text tells you to "verify in DevTools Network tab". That is safe ONLY because the OpenAI placeholder key returns a fast **401** — a completed, closed response. **Rule: never inspect a request body until the request has completed.** Never point devtools at `POST /api/chat` while it is streaming. The remediation is baked into `docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/spawn-frontend-inspector.md` — the frontend-inspector must read it.

**HAZARD 2 — P5-S4 (embedding model swap) can silently poison the shared corpus.**
Swapping the embedding model and then re-ingesting into `nag-corpus-spec28` risks leaving that collection with mixed-dimension / mixed-model vectors — which is *the very defect P5-S4 is hunting for*, but it would also **destroy the corpus phases 6 and 7 depend on**. Run P5-S4 against a **throwaway scratch collection**, never `nag-corpus-spec28`. Get my explicit consent before any ingestion during this phase.

**HAZARD 3 — never paste a real API key.** P5-S1 uses the literal placeholder `sk-test-PLACEHOLDER-DO-NOT-COMMIT` and nothing else. A real key entering this repo's logs or session dir is an incident, not a finding.

**HOUSEKEEPING — decision needed from me (Pilot), do not act unilaterally**: the Qdrant collection `poison-test-p4s5` and the local fixtures `~/Downloads/poison-p4s5*.md` are still live. verify-4 carried them forward for demo-prep cleanup. **But that collection is BUG-087's live reproduction** (deleted doc, orphaned vectors). Ask me before deleting. If we do delete, use the `collections.py` delete path (`delete_collection`), which DOES clean Qdrant correctly — the `DELETE /api/documents` path is precisely what BUG-087 says is broken.

---

**Phase 5 scenarios (from the playbook):**

- **P5-S1 — Add cloud-provider API key**: Settings → Providers → Add OpenAI key. Paste `sk-test-PLACEHOLDER-DO-NOT-COMMIT`. Save.
  Expected: key persists ("OpenAI · Configured"); **Fernet-encrypted at rest** — verify `sqlite3 data/embedinator.db "SELECT encrypted_key FROM provider_keys"` returns ciphertext, not plaintext; never plaintext in any log/UI/network panel; a chat attempt against OpenAI carries the key ONLY in the `Authorization: Bearer …` header (inspect the *completed* 401, per HAZARD 1).
- **P5-S2 — Stack restart with stored key**: `docker compose restart backend`, wait, re-open Settings.
  Expected: key still present, decryption transparent. A 401 is fine — what matters is the key survived and was used.
- **P5-S3 — Active model swap**: swap active chat model (`qwen3:14b` → an installed alt, e.g. `qwen2.5:7b`). Save.
  Expected: next chat uses the new model; trace + status indicator both reflect it (chat-header status text, model name in the trace stage).
- **P5-S4 — Embedding model swap**: swap embedding provider/model. Save. **Scratch collection only — see HAZARD 2.**
  Expected: either applied correctly on next ingestion, OR a clear "re-ingestion required" path. **NO silent inconsistency** where some chunks use the old embedder and some the new.
- **P5-S5 — Plaintext key audit (SC-012 enforcement)**: grep every surface for `sk-test-PLACEHOLDER` — rendered DOM (`document.body.innerText`), DevTools network panel filter, `docker compose logs | grep -i 'sk-test'`, `sqlite3 data/embedinator.db "SELECT query_text, reasoning_steps FROM query_traces"`, `grep -ri 'sk-test' data/`.
  Expected: **ZERO hits** in any rendered or logged surface. Encrypted bytes in SQLite don't count.
  **Any plaintext key leak is CRITICAL** — it violates Constitution V and SC-012 directly. Gate this one carefully; do not soften it.

**P5-S1 and P5-S5 are the SECURITY scenarios of this phase.** Phase 4 established the precedent: a real security failure gets CRITICAL, and "it resisted" gets framed as *emergent, not engineered*, unless you can point at the code that defends it. Hold that same line.

---

**RESUME ORDER (after the reads):**
1. Verify `docker context show` = `default`, then stack 4/4 healthy on system GPU. Confirm the `chrome-devtools` MCP responds to a trivial call before any hunt work.
2. Re-spawn the 3 always-on teammates in ONE response (RECOVERY mode, per §1):
   - `log-analyst` (python-expert/sonnet)
   - `frontend-inspector` (frontend-architect/sonnet) — **must read `spawn/spawn-frontend-inspector.md` first**, HAZARD 1 is baked in there
   - `bug-registrar` (technical-writer/sonnet) — **SOLE writer to `bugs/`**, and MUST tag every registration batch in `session-log.md` as `BugRegistrar | discovery`, never `Orchestrator | observation`. This held perfectly for all 12 Phase-4 registrations (verify-4 closed verify-3's WARNING-1 on it). **Do not let it regress.**
   Append `"RECOVERY MODE: read session-log.md before continuing"`. Wait for all 3 online + bug-registrar confirming **65 bugs / next-id BUG-089**.
3. Route the Phase-5-open phase-transition line to bug-registrar; brief me the Phase-5 scenario card; run the relay loop (§2). Observation grammar: `observation: P5.S<M> — …`. Bug IDs from **BUG-089**.
4. Work P5-S1..S5. Before minting any ID, have bug-registrar **dedup-check against the existing 65** — Phase 4's discipline (explicit dedup-check against sibling bugs before minting) is why verify-4 called the evidentiary rigor an improvement. Keep it.
5. Close Phase 5 (§3): findings schema-complete (real artifacts copied into the session dir; `title` ≤80 chars **excluding** the `BUG-0NN: ` prefix) → phase-transition entry → commit `docs/E2E/…` only → **MERGE** phase-5 into apply-progress preserving phases 0–4 → tell me to run verify-5.

Respect the PROHIBITED list (lead-prompt.md): no production edits outside the BLOCKER-PATCHED gate (Pilot Y/N required); Makefile + `embedinator.sh` SACRED; no severity downgrades; never close with an unfiled CRITICAL or untriaged MAJOR.

**START** by reading the files (steps 1–4) and verifying docker context + stack + GPU + chrome-devtools liveness, then give me a **5-line status** (docker context/GPU state, registry count, the P5 scenario list, chrome-devtools health, and the resume point = P5-S1) and **WAIT for my "go"** before spawning teammates.
