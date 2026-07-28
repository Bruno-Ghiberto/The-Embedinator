# Process — the prompts that drove the hunt

This directory holds the working artifacts behind the Round-1 bug hunt: the orchestrator
contract, the per-phase launch prompts, the independent gate prompts, and the boot contracts for
the agents that did the work. [`SUMMARY.md`](../SUMMARY.md) reports what the hunt found; this is
how it was run.

It is published because a result you cannot re-derive is a claim, not a finding. The 106 records
in [`bugs/`](../bugs/) are only as trustworthy as the method that produced them, and the method
is here in full — including the parts that went wrong.

## What is here

**`lead-prompt.md`** — the standing orchestrator contract. Roles, the per-phase relay loop, phase
close, write boundaries, the prohibited list, and the fallback when the agent-team harness is
unavailable. Re-pasted at the start of every phase; it is the one document that did not change.

**`apply-*.md`** — one launch prompt per phase, carrying that phase's scenarios, entry state,
hazards, and the corrections that earlier phases forced. These accumulate: `apply-7` opens with a
warning that the playbook's container names are stale, because using them would silently target
nonexistent containers and manufacture a phantom recovery PASS.

**`verify-*.md`** — one gate prompt per phase, written to be executed by a reviewer with **no
prior hunt context**. That independence is the point — a gate run by the agent that did the work
grades its own homework. Each gate carries a "known traps" section listing every false positive
an earlier gate produced.

**`spawn/`** — boot contracts for the three standing agents (log analyst, frontend inspector, bug
registrar), including the methodology hazards each accumulated as the hunt progressed.

**`agents/`** — the A1–A5 role manuals: mission, tool allowlist, read/write scope, output
template, and forbidden actions per role. The spawn documents override these where the two
disagree; precedence is stated in [`spawn/README.md`](./spawn/README.md).

## The two structural ideas

**A single writer.** Exactly one agent — `bug-registrar` — could write to the session directory.
Everyone else reported findings by message and parked captures outside the repository. Every gate
re-checked that boundary, which is why the registry has one voice and no lost edits.

**Independent gates.** Each phase closed against a reviewer that had never seen the phase run,
reading only the committed artifacts. Gates caught real problems the hunt had missed, and the
"known traps" lists exist because gates also produced false positives that had to be documented so
the next one would not repeat them.

## Re-running a phase

Read that phase's `apply-*.md` — it names its own entry state, its scenarios, and its
preconditions. The prompts assume you are at the repository root, that the stack is up, and that
the spec artifacts under [`specs/030-e2e-test-v3/`](../../../../specs/030-e2e-test-v3/) are
present; all of those are in the repository.

## What is not here

Stated plainly, because a repeatability claim that quietly omits its gaps is worth less than no
claim:

- **Phases 1–3 have no standalone launch prompt.** They were driven from `lead-prompt.md` plus
  the `resume-apply-*.md` documents, which is why those resume files carry so much state. Launch
  prompts as separate artifacts begin at `apply-4`.
- **`verify-1` and `verify-2` were not preserved.** The gates ran; the prompts were not kept as
  files. `verify-3` is the earliest surviving one, and later gates cite the verdicts of both.
- **The registry build and validation scripts are gone.** `apply-8` and `verify-8` reference
  `scratchpad/build_registry.py`, `scratchpad/validate.py`, and an isolated `jsonschema` venv.
  That directory was scratch space and was never committed. The schema they validated against
  *is* preserved, at
  [`contracts/bug-registry-schema.json`](../../../../specs/030-e2e-test-v3/contracts/bug-registry-schema.json),
  so the check is reproducible even though the exact scripts are not.
- **`apply-7-launch-prompt.md` was never executed.** It is the human-driven variant, superseded by
  `apply-7-autonomous-prompt.md` when phases 7–8 moved to autonomous execution. Both are kept: the
  diff between them is the clearest statement of what that change actually altered.
- **The spawn documents are pinned at `apply-3`.** Their "State Pins" sections still report 31
  bugs and a next ID of `BUG-055`. Later phases overrode them in the launch prompt rather than
  rewriting them, and `apply-7-autonomous-prompt.md` §3 says so explicitly.

## One edit was made at publication

These files lived outside the repository while the hunt ran. Copying them in required rewriting
their internal paths — the old location and the author's absolute home directory — so the
references resolve where the files now sit. Nothing else was changed: no findings were softened,
no corrections removed, no hazards trimmed. The stale state pins, the superseded prompt, and the
mid-phase corrections are all preserved as written.
