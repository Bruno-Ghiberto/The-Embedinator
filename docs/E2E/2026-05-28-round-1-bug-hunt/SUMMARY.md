# Round 1 End-to-End Bug Hunt — Summary

**The Embedinator** · branch `030-e2e-test-v3` · hunt closed 2026-07-28
**106 findings**, `BUG-024`–`BUG-129` · **55 of them severe enough to triage**, all with public
GitHub issues · **zero production files changed** during the hunt

---

## What this was

A running instance of the product was driven through 36 scenarios across seven phases — cold
start, document ingestion, ordinary chat, adversarial chat, settings, observability, and recovery
from failure — and everything that went wrong was written down. Dependencies were deliberately
killed mid-operation. Nothing was fixed while the hunt was in progress; the point was to find, not
to repair.

This document is the result. It is written to be readable without knowing the codebase.

---

## The finding that justifies the method

The single most repeated defect in this codebase is a mechanism that **exists, is correctly
written, has configuration options, and can never run**, because the one path that would call it
is gated behind something that makes it dead.

This happened four independent times, in four different subsystems, found by four different
scenarios:

| Mechanism | Why it can never run |
|---|---|
| Citation validation (`BUG-107`) | The graph builder has never accepted a `reranker` argument, so the node's first line always returns early. Citation quality assurance is a 100% no-op on every request. |
| Graceful-shutdown guard (`BUG-121`) | The "we are shutting down" flag is set *after* the point where the server has already stopped accepting the shutdown. It can never be true for a request that is still in flight. |
| WAL checkpoint + checkpointer close (`BUG-121`) | The drain is unbounded, but the container is given 15 seconds before it is killed. The kill always wins. |
| Inference circuit breaker (`BUG-118`) | All three of its call sites sit inside a verification function that returns early because the feature flag governing it is off by default and was off at runtime. It never checks, never counts, never opens. |

**This is why an end-to-end hunt found what other techniques did not.** None of these look broken
on review — the mechanism itself is correct. Unit tests pass, because the unit is fine. Static
analysis is satisfied, because the code is well-formed. The defect is not *in* the mechanism; it
is in the absence of a caller, and that is only visible when you run the whole system and then
break something to see whether the mechanism responds.

There is a sharper version of this. The codebase contains **three separate circuit-breaker
implementations**, and the hunt observed all three:

| Breaker | Outcome |
|---|---|
| Qdrant client (`storage/qdrant_client.py`) | **Works exactly as specified.** Opened at 5 failures, half-opened 60.065s later, probed, recovered — threshold and cooldown both confirmed empirically. |
| Retrieval path (`retrieval/searcher.py`) | Reachable, but miscounts: it treats client-side 4xx errors as service failures, so one bad collection degrades all retrieval for 60s (`BUG-099`). |
| Inference path (`agent/nodes.py`) | **Can never fire** (`BUG-118`). |

One works, one miscounts, one is unreachable — the same idea implemented three times with three
different outcomes. That is a more useful thing to know about a codebase than any bug count.

---

## What else the findings had in common

Four further patterns recur across the registry.

**State is written and never read.** The entire Settings page persists to the database, reads back
correctly through the API, and is consumed by nothing at runtime (`BUG-095`). Seven load-bearing
options are inert — including one that a user would reasonably believe switches off an entire
verification stage. The user is not lied to by any single message: the save really did succeed,
and reloading really does show the new value. The deception is structural. Persistence is
presented as configuration.

**Records are written only when things go right.** All 79 ingestion jobs, including the one that
failed, have a null completion timestamp (`BUG-110`). The query trace table writes its single row
at step 8 of 9, and its schema has no column capable of expressing "aborted" — so a killed request
leaves no row at all (`BUG-116`). Meanwhile `/api/health` returned 200 OK twenty-one consecutive
times through a request that had been wedged for 160 seconds (`BUG-046`). A dead request is
indistinguishable from an idle server on every surface the product offers.

**Failure gets blamed on the user's data.** With the inference engine stopped, a chat turn
completed cleanly in 21.5 seconds and told the user *"I could not find any relevant information to
answer… The indexed documents may not cover this topic"* (`BUG-126`). The document in question was
in the corpus and had been retrieved successfully minutes earlier. Because the retrieval
orchestrator is itself driven by the language model, an unreachable model means no search is ever
issued at all — so a perfectly healthy vector database is simply never asked, and the empty result
is reported as a coverage problem. The user's next step becomes re-ingesting documents that were
never the problem. The health endpoint knew the truth throughout, returning 503 with the real DNS
error; the chat path never asked it.

**A user cannot tell working from broken.** Two screenshots taken 189 seconds apart — one of a
healthy conversation generating an answer, one of a conversation that was already permanently dead
— differ only in the blink phase of the text cursor (`BUG-119`). There is no client-side timeout
anywhere. The only liveness signal the product offers is global page chrome, which cheerfully
recovers to "Backend connected" once the server restarts, while the conversation underneath it can
never complete. The user is not merely misinformed; the interface actively invites them to keep
typing into a conversation that cannot deliver.

That last one comes with an unusually precise control case. An accidental HTTP 500 during a
scenario showed that when a response carries a non-OK HTTP status, **the error path works
correctly** — the spinner clears, the error renders, a Retry button appears. It fails *only* when
an already-successful stream is terminated at the transport layer. So the defect is not "error
handling is missing." It is: error handling exists for HTTP-status failures and is entirely absent
for transport termination of an in-flight stream. Stated that tightly, it is one bug, and it is
fixable.

---

## What actually works

A hunt that reports only failures is not a credible hunt. Four behaviours were tested
adversarially and passed, and each one is attributable to specific code rather than to luck — the
standard the later phases held themselves to was that a clean result counts only if the
engineering producing it can be named.

| Behaviour | Evidence |
|---|---|
| **Ingestion survives a three-minute vector-database outage with zero data loss** | The buffer held all 11 pending chunks and flushed them on recovery: `ingestion_job_paused_qdrant_outage pending=11` → `ingestion_job_resumed_qdrant_recovered flushed=11`. Final state fully consistent — job completed, 11 chunks, 13 vector points, verified per document with exact counts. Engineered at `ingestion/pipeline.py:481-495`, whose docstring reads *"Pause job, poll for Qdrant recovery, flush buffer, resume."* |
| **The Qdrant circuit breaker behaves exactly as specified** | Opened at `failure_count=5` against a threshold of 5; half-opened 60.065 seconds later against a 60-second cooldown; probed and recovered. |
| **Graph state survives an unclean kill, and its integrity is verified on restart** | 13 checkpoints intact after `docker kill`; startup logged `storage_checkpoint_integrity_ok` (`main.py:578`). A full-stack restart preserved 81 documents, 81 jobs, 1,014 traces, 26 collections and 7 settings, with the stored provider key still encrypted at 140 bytes. |
| **Health detects a dead dependency immediately and accurately** | HTTP 503, `status: degraded`, `ollama=error` carrying the real DNS cause, with the other dependencies correctly still reported healthy — and back to 200 within about two seconds of recovery (`health.py:60`, `:67-68`). |

**The contrast is the point.** The same codebase that leaves a chat spinner running forever also
buffers ingestion through a three-minute outage and loses nothing. Quality here is *uneven*, not
absent — which is a more useful thing to tell a reader than a bug count, and a more accurate one.

Two qualifications, because both belong with the passes rather than after them. First, the
ingestion recovery covers "the dependency comes back" and there is **no engineered behaviour for
"it does not"** — the scenario passed only because Qdrant returned (`BUG-128`). Second, the
restart test proves nothing was lost, but it also proves the application's own durability
guarantees were never exercised: the system relied on SQLite's crash safety instead of the
shutdown path written for the purpose (`BUG-121`). Neither qualification cancels its pass. Both
are why the passes are trustworthy.

---

## The numbers

| Severity | Count | | Layer | Count | | Phase | Findings |
|---|---:|---|---|---:|---|---|---:|
| BLOCKER | 1 | | Backend | 48 | | P1 Cold Start | 15 |
| CRITICAL | 11 | | Frontend | 40 | | P2 Ingestion | 16 |
| MAJOR | 43 | | Ingestion | 6 | | P3 Chat Happy Path | 22 |
| MINOR | 45 | | Reasoning | 4 | | P4 Chat Edge Cases | 12 |
| COSMETIC | 6 | | Infrastructure | 3 | | P5 Settings & Providers | 13 |
| | | | Observability | 3 | | P6 Observability | 16 |
| **Total** | **106** | | Retrieval | 2 | | P7 Recovery & State | 12 |

All 55 findings graded MAJOR or above carry a triage decision, a written rationale, and a live
public GitHub issue — **39 scheduled for the v1.0 fix wave, 16 deferred to v1.1**, issues `#123`
through `#177`, verified one-to-one against the registry with no duplicates and no gaps. The
severity distribution is deliberately bottom-heavy: 51 of the 106 are MINOR or COSMETIC and are
registered as backlog, not as sprint scope. Full breakdown and fix sequencing in
[`triage.md`](./triage.md); the launch recommendation is in
[`LAUNCH-DECISION.md`](./LAUNCH-DECISION.md).

The registry validates against its JSON Schema with **zero violations across all 106 records**,
checked by two independently written parsers. Every record carries severity, layer, discovery
timestamp, scenario, numbered reproduction steps, expected versus actual behaviour, and at least
one artifact reference.

---

## How the hunt ran

Seven phases, 36 scenarios, executed against a live four-service stack. Each phase opened and
closed with a timestamped entry in an append-only session log, and each closure was reviewed by a
separate verification gate that re-derived every count from files on disk, from `git`, and from
the live GitHub API rather than accepting the phase's own report. Seven such gates ran; all seven
passed. The final gate was run by a reviewer given **no prior hunt context at all**, and it caught
a real scoping defect in its six predecessors: their schema checks had validated only each
phase's *new* records, leaving fourteen registry-wide violations alive across six gates. Those
were found and repaired before closure, and the registry today validates clean end to end — but
the earlier "zero violations" statements were narrower than they read, and that is recorded rather
than quietly corrected.

Three findings about the *method* are worth recording, because they change how much weight the
results carry.

**Single attempts would have graded scenarios without testing them.** Phase 7's kill-mid-stream
scenario needed four attempts. The first three missed the premise entirely — one hit an unrelated
wedge with nothing streaming, two hit turns that had already completed. Only the fourth landed a
true mid-generation kill, six chunks into visible token output. A single-attempt run would have
recorded a verdict for a card it never actually exercised.

**Refuted hypotheses were kept, not dropped.** A prediction that resumed ingestion jobs would
claim writes that never landed was disproven by exact per-document vector counts, and is recorded
*as refuted* — because otherwise a later reader re-forms the same hypothesis and re-tests it.

**Escalations were declined when the evidence was thin.** A proposal to raise `BUG-069` to
CRITICAL was audited and refused: the complete evidence base was two hard failures with no third
occurrence and no controlled series, which is consistent with the proposed mechanism but does not
establish it. It stands at MAJOR with the declined case preserved in the record so it can be
re-weighed rather than re-derived.

### A note on scenario identifiers

`P3-S7` appears in four records but is **not a playbook scenario**. Phase 3 ran six scenarios,
`P3-S1` through `P3-S6`, plus an exit checklist. `P3-S7` is a synthetic bucket assigned during a
later normalisation pass so those four exit-checklist findings would satisfy the schema's scenario
pattern; the original provenance is preserved verbatim on each record. Phase 3 had six scenarios,
not seven.

---

## What was mechanically enforced, and what is only attested

Phase 7 ran under a documented amendment that changed how the hunt was executed. Two of its
clauses can be verified from the repository. Two cannot. Stating which is which is the honest
thing to do, and the independent verifier called the distinction *"a credibility asset, not a
liability."*

**Mechanically enforced — verifiable by anyone with the repository:**

- *No destructive commands.* The prohibition on volume-destroying operations is not discipline; it
  is a deny-list in `.claude/settings.local.json` covering `docker compose down -v`,
  `docker volume rm`, `docker volume prune`, `docker system prune`, `make clean` and `rm -rf`. A
  matching command fails at the harness rather than executing. The one apparent match in the
  session log is Phase 1 prose describing what the playbook *specified*, not a command that ran.
- *No inline fixes during the final phase.* Every one of the 106 records carries
  `BLOCKER-PATCHED: no`; there are zero patch-gate approvals in the session log. Both counts are
  zero, and they match.
- *No production code changed.* The diff against a freshly fetched `origin/develop`, scoped to
  `backend/`, `frontend/`, `ingestion-worker/`, the Makefile, the launchers and the compose files,
  is **empty**. The closing commit touches 68 files, all inside the hunt's own session directory.

**Self-attested — declared once in the log and not falsifiable from repository artifacts:**

- That Phase 7's browser scenarios were driven through Playwright rather than the debugging
  protocol. The *negative* half of this claim is verifiable and clean — the blocking call that
  caused a 30-minute stall in an earlier phase appears zero times in the Phase 7 range, and the
  alternative tool is declared unused — but the positive claim rests on a single declaration,
  corroborated only circumstantially by the artifacts on disk.
- That the three teammate agents ran on a higher-capability model tier for the final phase. Their
  roles, count and write boundaries are independently confirmed; the model tier is not recoverable
  from the repository.

---

## Where the instruments failed

Eight times during the final phase, a reading was wrong. They fall into **two classes that need
different mitigations**, and merging them produces a limitation statement that covers only half the
evidence.

**Class A — instrument faults.** The tool returned wrong or incomplete data. Re-reading later
returns the *same* wrong answer; these are not timing problems.

1. A text search rendered the literal token `circuit` as `n` in its own output.
2. A health-polling script left the *previous* response body in place when a request timed out, so
   a stale sample could pass for a fresh one.
3. `docker compose logs -f > file` did not flush; `docker logs -f <container>` did.
4. `docker compose down` destroyed the container logs that were about to be needed — one shutdown
   sequence is permanently unrecoverable as a result.

*Mitigation: cross-check a tool's output against a second, independent tool.* That is in fact what
caught all four.

**Class B — sampling faults.** The tool was correct; the *moment* was wrong.

5. An ingestion job read as `completed` — legitimately true. It had finished 0.64 seconds before
   the fault landed. Checking its timestamp against the container's own stop time is what
   prevented a spectacular false CRITICAL ("ingestion reports success during an outage").
6. A mid-recovery transient read 29 seconds before a buffer flush was indistinguishable from
   permanent corruption. It nearly produced a CRITICAL for a scenario that in fact passed.
7. A counter file read mid-write came back one behind, and was nearly filed as a sequence
   violation.
8. A registry census taken before the last record was written reported one short.

*Mitigation: re-read after the mutating operation settles* — here, after the 60-second breaker
cooldown.

**Six of the eight were caught by their own author. Two were the orchestrator's.**

The rule that came out of fault 6 was then actually applied to the finding most exposed to it:
`BUG-124` grades a recovery window and states that it was reproduced twice, on a live page and on
a cold page load, with its measurement deliberately preserved as a 31–60 second bracket rather
than a fabricated point value.

**The two statements this round stands behind:**

- Findings resting on a single read of a mutating source are provisional.
- Findings resting on a single tool's output were cross-checked against a second tool; where that
  was not possible, the finding is marked accordingly.

One record genuinely rests on uncontrolled single observations — and it carries `UNCONFIRMED:` in
its own title so the qualification survives being read in a list, states its evidence *against*
explicitly, is deferred to v1.1, and is cited nowhere else as established (`BUG-123`). Two further
sub-claims were withdrawn as unproven rather than shipped.

Naming these is what makes the other findings weighable. A reader who knows where the instruments
failed can calibrate the rest; a reader shown only clean results has to take all of it on trust.

---

## Repeatability

The hunt is re-runnable, and that is the point of writing the process down rather than only the
results. Four families of prompt artifact live under `notes/Process/spec-30-r1-sdd/`:

- **`lead-prompt.md`** — the standing orchestrator contract: roles, write boundaries, prohibitions.
- **`apply-*-prompt.md`** — one launch prompt per hunt phase, carrying that phase's scenarios,
  entry checklist and deviations.
- **`verify-*-prompt.md`** — one gate prompt per phase, written to be executed by a reviewer with
  no prior context, which is what makes the gates independent.
- **`spawn/spawn-*.md`** — role definitions for the three teammate agents, including the
  methodology hazards each accumulated as the hunt progressed.

Alongside them the session directory holds the append-only session log, the 106 records, and the
schema they validate against. Re-running a phase means re-reading its prompt, not reconstructing
what was done.

---

## Where to go next

- **[`triage.md`](./triage.md)** — the fix-wave input: 39 v1.0 items grouped by layer and ordered
  by blast radius, plus the 16 deferrals with their rationales and the four open questions carried
  forward.
- **[`LAUNCH-DECISION.md`](./LAUNCH-DECISION.md)** — the structured GO / NO-GO, with the two
  findings that break the first-contact demo path called out specifically.
- **`bugs/`** — all 106 records, one file each.
- **GitHub issues `#123`–`#177`** — the 55 triaged findings, publicly tracked.
