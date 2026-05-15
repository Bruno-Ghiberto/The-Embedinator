# Contract — BLOCKER-PATCHED Gate Protocol

**Spec**: 030-e2e-test-v3
**Phase**: 1
**Status**: locked

Defines the orchestrator prompt shape, Pilot Y/N response constraints, and session-log capture template for the narrow BLOCKER-PATCHED inline-fix exception (FR-011, FR-012, FR-013, FR-016, SC-005).

## When this contract fires

ONLY when ALL of the following are true:
- A defect is discovered (any phase 1–7).
- The defect severity is BLOCKER (FR-007 — "Hunt cannot continue").
- Without an inline patch, the hunt cannot proceed (FR-011 (a)).
- A minimum-viable unblock-fix exists that satisfies:
  - Takes ≤5 minutes (FR-011 (b))
  - Is zero-risk (FR-011 (c))
  - Has MINOR or COSMETIC scope (FR-011 (d))

If ANY constraint fails, the orchestrator does NOT propose the gate. Instead: register the BLOCKER, log "hunt cannot continue", and close the hunt early (FR-014 still applies — the BLOCKER is filed; the next round or spec-31 picks it up).

## Orchestrator prompt (pane 2 → Pilot pane 1)

```text
BLOCKER-PATCHED proposal for BUG-XXX
═══════════════════════════════════════════════════════════════════════════════
Defect: <one-line summary of the BUG>
Severity: BLOCKER
Phase scenario: P<N>-S<M>

Proposed patch
──────────────
<one-paragraph diff sketch with explicit file paths and line ranges>
Example:
  Edit `frontend/components/Citation.tsx` lines 42–48:
  Replace `text.normalize()` with `text.normalize('NFC')` to handle Spanish
  accents in the citation index lookup.

Patch scope: MINOR | COSMETIC                # NEVER MAJOR/CRITICAL/BLOCKER
Estimated time: <N> minutes                  # MUST be ≤5
Risk assessment: zero-risk because <one sentence concrete reason>
  Examples:
    - "single-line string change, no logic"
    - "CSS rule only, no behavioral impact"
    - "log-format string, output not parsed downstream"

What happens on Y: Inline Fixer dispatched with the above prompt. Commit
  lands within the estimated time. Bug record updated with commit SHA + your
  authorization timestamp. Severity remains BLOCKER (FR-013).
What happens on N: Hunt is paused. BUG-XXX remains registered with full
  reproduction. Phase is descoped if possible; if not, hunt closes early.
  NO retry of this proposal.

Your decision [Y/N]:
═══════════════════════════════════════════════════════════════════════════════
```

## Pilot response constraints

- Pilot's response MUST be exactly `Y` or `N` (single character, case-insensitive accepted).
- An optional one-line rationale MAY follow on the same line, separated by ` — ` (e.g., `N — risk justification too thin, want full review`).
- The Pilot has unlimited time to decide. The hunt's 12h time-box pauses during gate deliberation (capture pause start/end in session-log if it exceeds 60s).
- The Pilot MAY reject without rationale.
- The Pilot MAY NOT modify the patch terms (e.g., "Y but only lines 42–45"). If the proposal is wrong, the answer is N and the orchestrator drafts a new proposal — which counts as a separate gate event.

## Session-log capture format

The orchestrator MUST emit two timestamped session-log entries for every gate event — one for the proposal, one for the response:

```
[YYYY-MM-DD HH:MM:SS] Orchestrator | gate | BLOCKER-PATCHED proposal for BUG-XXX:
  Defect: <one-line summary>
  Severity: BLOCKER
  Proposed patch: <one-paragraph diff sketch>
  Patch scope: MINOR | COSMETIC
  Estimated time: <minutes>
  Risk assessment: zero-risk because <one sentence>
  Pilot decision: pending
[YYYY-MM-DD HH:MM:SS] Pilot | gate | Y                # or N
   — <optional one-line rationale>
```

If Pilot answers `Y`: append a third entry after the commit lands:

```
[YYYY-MM-DD HH:MM:SS] InlineFixer | gate | BUG-XXX patch committed <SHA>
   files: <paths>
   time elapsed: <seconds>
```

## Bug record cross-references

When `Y` flows through:

- Bug record `blocker_patched.applied` → `true`
- Bug record `blocker_patched.commit_sha` → the InlineFixer commit SHA
- Bug record `blocker_patched.pilot_authorization_timestamp` → the `Pilot | gate | Y` line's timestamp (verbatim)
- Bug record `blocker_patched.patch_summary` → the orchestrator's "Proposed patch" paragraph (verbatim)

These cross-references are enforced by the JSON schema validation at Phase 8.

## Inline Fixer dispatch (orchestrator side)

The orchestrator dispatches via Agent Teams Lite:

```text
Agent({
  description: "BLOCKER-PATCHED inline fix for BUG-XXX",
  subagent_type: "python-expert" | "backend-architect" | "frontend-architect",
                                    # pick by layer
  prompt: "
    Spec-30 BLOCKER-PATCHED inline fix.
    Bug: BUG-XXX — <one-line summary>.
    Make EXACTLY this change: <verbatim proposal paragraph>.
    Constraints:
      - Time budget: <minutes>.
      - Scope: MINOR or COSMETIC only (do NOT generalize, refactor, add tests).
      - Write one focused commit with message:
        'fix(spec-30): BLOCKER-PATCHED — <one-line summary> (BUG-XXX)'
      - Report the commit SHA on return.
    Do NOT touch Makefile, embedinator.sh, embedinator.ps1.
    Do NOT modify any file outside the proposal's stated paths.
  ",
  model: "sonnet"
})
```

The dispatch is recorded as a `dispatch` session-log entry before the Inline Fixer runs.

## Rejection consequences

On `N`:
1. Orchestrator does NOT dispatch the Inline Fixer.
2. Bug record remains BLOCKER, `blocker_patched.applied` stays `false`.
3. Orchestrator evaluates: can the current phase be descoped to skip the blocker? If yes, log the descope decision and continue. If no, close the hunt early with Phase 8 invoked immediately.

## Multiple gates per session

The 12h time-box accommodates multiple gates if they arise. Each gate is independent: prior `Y` outcomes do not auto-authorize subsequent gates; prior `N` outcomes do not bias subsequent gates. Each is presented fresh with full risk justification.

The Phase 8 closure check (SC-005) requires EVERY `blocker_patched.applied=true` entry in the registry to have a matching session-log Y entry. A mismatch (e.g., an applied patch without a recorded Y) blocks closure.

## Why this gate exists

From engram #848 (2026-05-06):
> "User's discipline observation: opportunistic fixes during a hunt = derailment.
>  Methodology > opportunism. This is the same insight QA teams use for smoke cycles."

The BLOCKER-PATCHED exception exists because — and ONLY because — the hunt cannot continue with a true blocker in place. Every patched-blocker is still registered with full reproduction so spec-31 can re-fix it properly. The gate's narrowness (≤5min, zero-risk, MINOR/COSMETIC, Pilot Y/N) is what makes the exception non-leaky.
