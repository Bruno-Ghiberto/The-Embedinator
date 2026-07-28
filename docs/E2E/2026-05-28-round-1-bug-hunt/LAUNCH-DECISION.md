# Launch Decision — v1.0.0

**Decision date**: 2026-07-28, at registry freeze
**Scope of this decision**: tagging `v1.0.0` and presenting the product as ready to run. It is not
a decision about the repository being public — it already is — nor about the hunt artifacts, which
ship as they are.
**Basis**: the frozen Round 1 registry — 106 findings, `BUG-024`–`BUG-129`. See
[`SUMMARY.md`](./SUMMARY.md) and [`triage.md`](./triage.md).

---

## Verdict: **NO-GO**

Not because the codebase is weak — Round 1 recorded four adversarially-tested passes with the
engineering behind each one cited — but because **the first thing a new user does is one of the
things most likely to fail, and it fails silently**.

Two findings decide this on their own. Both sit directly on the first-contact path.

### `BUG-054` — the first chat after startup hangs forever, with no error

A ~30-second idle timeout in the proxy layer cuts any request whose first processing step takes
longer than that. A controlled A/B isolated the variable precisely: the wedged run's first silent
gap was **33.34 seconds** and it never recovered; the completed run's was **2.38 seconds**. The
only difference between them was which side of the timeout that gap fell on.

With the local model's keep-alive observed at roughly five minutes, the request that reliably
crosses it is **the first chat after `docker compose up` — or any chat after five idle minutes**.
For a self-hosted project that someone clones, starts, and tries, that is close to the modal first
interaction.

It is not only cold starts. The same wedge reproduced on a warm model at turn 4 of an accumulating
conversation, running **383 seconds with no timeout firing at any layer**. Nothing ends that
request: the 300-second research-loop budget is scoped to a loop the wedge never reaches, the
conversation graph contains no timeout or wait-for call at all, and the client has no watchdog.
Meanwhile the container reports `Up (healthy)` throughout.

What the user sees is a spinner that never stops. What `BUG-074` and `BUG-119` add is that the
spinner stays running even after the backend fully recovers, and that a dead conversation is
pixel-identical to a working one. An identical query issued directly to the backend, bypassing the
proxy, completed in 13 seconds — so the cut is at the proxy, and the fix surface is narrow.

### `BUG-126` — when the model is down, the product blames the user's documents

With inference stopped, a chat turn completed cleanly in 21.5 seconds and reported: *"I could not
find any relevant information to answer… The indexed documents may not cover this topic."* The
document was in the corpus and had been retrieved successfully minutes earlier in the same
session.

The mechanism is worse than a bad error message. The retrieval orchestrator is itself driven by
the language model, so with the model unreachable **no search is ever issued** — the vector
database, entirely healthy, is never queried once. The answer path genuinely sees zero results and
has no branch distinguishing "searched and found nothing" from "never searched."

The user's actionable next step becomes re-ingesting a corpus that was never the problem. And the
information needed to tell them the truth existed in the same process at the same moment:
`/api/health` was returning 503 with the real DNS error throughout. Health knew; the chat path
never asked.

A demo where the model is slow to load and a demo where the model is unavailable are the two most
likely first-run failure modes for a self-hosted local-inference product. The product handles one
by hanging silently and the other by misdiagnosing the user's data.

---

## The quantitative basis

| Measure | Value |
|---|---|
| BLOCKER | 1 — `BUG-045`, **already fixed** on `develop` (PR #101, `d9107cb`) |
| CRITICAL | **11**, all triaged `v1.0-fix` |
| MAJOR | 43 — 27 `v1.0-fix`, 16 `v1.1-defer` |
| Total triaged (MAJOR+) | 55, all with live GitHub issues `#123`–`#177` |
| **v1.0-fix scope** | **39 records — 38 outstanding**, the 39th being the already-fixed BLOCKER |
| MINOR / COSMETIC | 51 — registered backlog, not launch-blocking |

Every CRITICAL is scheduled for v1.0. None was deferred. That is the shape of a codebase that is
close but not there: nothing in the severe tier was judged acceptable to ship, and none of it was
judged unfixable either.

---

## Conditions to convert to GO

1. **All 11 CRITICALs closed and verified end-to-end**, not unit-tested. Every one of them was
   invisible to unit tests; re-verifying them the same way that missed them proves nothing.
2. **`BUG-054` and `BUG-074` fixed and re-run on a genuinely cold stack** — model unloaded, first
   chat issued through the proxy, not directly to the backend. This is the single highest-value
   check on the list.
3. **`BUG-126` fixed such that a dependency outage produces a message naming the outage**, using
   the health state that already exists in-process.
4. **The configuration-honesty cluster closed together** — `BUG-095` and `BUG-047` must land in the
   same wave, because either alone leaves the wrong model silently running.
5. **`BUG-052` closed** — re-upload must not destroy the old document's vectors before the new
   ingest succeeds. It is the only finding in the registry that destroyed user data during the
   hunt: 2,025 vectors, permanently, with no rollback and no notification.
6. **A cold-start measurement re-run** (see carry-forward 1 below).

The 27 `v1.0-fix` MAJORs should be worked in the sequence given in
[`triage.md` §5](./triage.md#5-suggested-sequencing-for-the-fix-wave), which is grouped so that
fixing the head of each cluster shrinks or removes what follows.

---

## Open carry-forwards

These are not findings. They are places where this decision rests on less evidence than it appears
to, and they must not vanish at closure.

### 1. The cold-start measurement was taken warm

The Phase 1 startup budget — all four services healthy in about 27 seconds, within both the
per-service and total budgets — was measured after `docker compose down` **without** `-v`. Volumes
were preserved. It is therefore a **warm-volume start, not a true cold start**: model weights,
caches and index data were already present on disk.

The deviation was recorded at the time it happened, not reconstructed afterwards. But it means the
startup figure understates a genuine first-run, which is exactly the path this decision most cares
about. The gap matters more than usual because `BUG-054`'s trigger is a slow first operation, and
a real cold start makes the first operation slower.

Under the hunt's own operating amendment, volume-destroying commands are blocked at the harness —
so within the hunt's window this could only ever be a caveat. **The cold-start figure must either
be re-measured outside that window before v1.0.0 is tagged, or the published startup number must
carry the warm-volume qualification explicitly.** It should not be quoted bare.

### 2. Secret hygiene (SC-012) was never re-audited against the observability sinks

The plaintext-key audit in Phase 5 was thorough, and it is the hunt's one *engineered* security
pass — guards named on both the backend and frontend paths, re-run after a restart, model swaps
and a stack-trace storm, and clean on every surface including the raw on-disk container logs and
the database's own bytes.

But Phase 6 then examined three surfaces that audit never covered:

- `BUG-117` — Trace Detail renders citation data through a raw `JSON.stringify` dump.
- The `query_traces` table, which persists query text and reasoning steps.
- `BUG-116` — the absent log/event surface, which is what a future fix would most naturally add.

The Phase 5 audit predates all three. Its own governing standard was that *a pass never re-tested
after the state changed is not a pass* — and the state changed. Phase 7 added an adjacent data
point (`GET /api/providers` returns a boolean, and the stored key remained encrypted at 140 bytes
across a full restart), but that is not the same audit.

**This is an outstanding check, graded as a suggestion at the Phase 6 gate. It should be closed
before v1.0.0, not carried further.**

### 3. Four questions were deferred, not answered

Recorded in [`triage.md` §7](./triage.md#7-open-questions-carried-to-spec-31): the `BUG-123` proxy
isolation probe, the `BUG-069` turn-depth series, a withdrawn WAL-ordering hypothesis, and a
semaphore-exhaustion probe that was skipped by explicit decision. None claims a verdict. Their
absence is a choice, not an omission — but `BUG-123` in particular sits on the same proxy layer as
`BUG-054`, and confirming or retracting it would sharpen that fix.

---

## What is not in question

The NO-GO is narrow, and it should not be read as a judgement on the whole system.

Ingestion buffered eleven pending chunks through a three-minute vector-database outage and flushed
every one on recovery, verified per document with exact counts. The Qdrant circuit breaker opened
at its configured threshold and half-opened 60.065 seconds later against a 60-second cooldown.
Thirteen graph checkpoints survived an unclean kill and their integrity was verified on restart. A
full-stack restart preserved 81 documents, 81 jobs, 1,014 traces, 26 collections and 7 settings,
with the stored provider key still encrypted. Health detection of a dead dependency was immediate,
accurate and correctly scoped to the failing service.

Each of those is attributable to named code. The gap between them and the failures on the demo
path is the actual story of this codebase: **the durability and recovery work is real; the
user-facing failure surface is not built yet.** That is a fixable asymmetry, and the 38 outstanding
v1.0 items are the work of fixing it.

---

## Re-decision gate

Re-open this decision when the v1.0 fix wave reports complete. The re-decision requires:

- the 11 CRITICALs closed, each re-verified end-to-end against the scenario that found it;
- a cold-start run from destroyed volumes, with the first chat issued through the proxy;
- the observability-sink secret audit closed;
- and a short re-run of the Phase 7 recovery scenarios, which are the ones that most reliably
  distinguish "the fix works" from "the fix compiles."

Round 2 should not repeat Round 1. Its highest-value target is the class Round 1 named but only
sampled: **mechanisms that exist, are correct, and are never called.** Four were found by
accident, in four different subsystems, by four different scenarios. Nobody went looking for them.
