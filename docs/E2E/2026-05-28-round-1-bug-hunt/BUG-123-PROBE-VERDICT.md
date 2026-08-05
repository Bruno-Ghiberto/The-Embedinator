# BUG-123 isolation probe — verdict

**Spec-31 tasks 1.6 (probe) and 1.7 (verdict). Decision artifact — this is a fork input for Batch 2, not a fix.**

- **Date**: 2026-08-05
- **Verdict**: **BUG-123 CONFIRMED**
- **Consequences**: v1.0-fix scope moves **38 → 39**; design decision **D3 Branch T activates** (spec-31 task 2.4)
- **Evidence**: [`public-evidence/BUG-123-isolation-probe.log`](public-evidence/BUG-123-isolation-probe.log) · instrument: [`public-evidence/BUG-123-isolation-probe.py`](public-evidence/BUG-123-isolation-probe.py)

> The stored instrument is the `ruff format`ted copy of the script that produced the log. The
> committed bytes differ from the executed ones only by line wrapping to the repo's 120-column
> limit — three joined lines, no semantic change. Noted rather than hidden, because an evidence
> artifact that silently differs from what ran is not evidence.

---

## Why a probe was needed

BUG-123 was registered **UNCONFIRMED** on purpose. It rested on two observations that were
never controlled for the variable they blamed:

| | Path | Client | Result |
|---|---|---|---|
| P7-S1 | proxied `:3000` | browser fetch reader + an in-page `tee()` | no EOF for 189s |
| P7-S1d | direct `:8000` | `curl` | terminated promptly |

Different clients, different turn states, one observation each, no re-kill. The record's own
Notes say a defect must not be asserted on evidence that has not isolated its variable, and
the recommended next step was a probe with *identical query and turn state, killed twice, once
proxied and once direct*.

## Method

Every variable held fixed except the path under test:

- identical request body, model (`qwen3:14b`) and collection on all four runs
- the **same** client and the **same** reader on both paths — this is what P7-S1/P7-S1d lacked
- kill fired at the **same point in the turn**: after exactly **3 `chunk` frames**, so the
  backend is mid-generation and doing the same work when it dies (matching P7-S1d's
  mid-generation kill; killing on the first frame would land on `session`, which
  `backend/api/chat.py:148` emits before it even takes the semaphore)
- `docker kill embedinator-backend`, then `docker start` + `/api/health/live` readiness between runs
- **each path killed twice** — BUG-123 was never checked for reproducibility
- post-kill reader budget **120.0s** idle before declaring `still_open`

`eof_reason` is **imported from `tests/e2e_real/ndjson.py`**, not redefined, so the taxonomy
this verdict writes is the one Batch 2's fork reads. Its docstring already names the outcome:
`still_open` is "the BUG-123 signature when it happens through the Next.js proxy but not
against the backend directly."

### Instrument choice — the Docker stack, not `tests/e2e_real`

`tests/e2e_real/README.md` records a **host-loopback artifact**: proxied requests stall inside
the backend before the graph runs, and it states the proxy fixtures are not the instrument for
the proxy class. Running this probe there would have reproduced the very defect the probe
exists to rule out. Both paths were smoke-tested on the Docker stack first and both reached
generation, so the artifact is confined to the pytest fixtures.

## Result

| Run | Path | `eof_reason` | kill → EOF | terminal event | events | backend at EOF |
|---|---|---|---|---|---|---|
| #1 | proxied `:3000` | **`still_open`** | never (>120s) | no | 13 | `exited` |
| #1 | direct `:8000` | **`peer_closed`** | **0.3s** | no | 13 | `exited` |
| #2 | proxied `:3000` | **`still_open`** | never (>120s) | no | 13 | `exited` |
| #2 | direct `:8000` | **`peer_closed`** | **0.3s** | no | 13 | `exited` |

Reproduced 2/2 on each path. All four runs saw the same 13 events and the same kill point.

### The failure is in the system under test, not the instrument

The harness README requires every reproduction to carry a companion assertion that the failure
came from the product rather than the reader. Here the **direct path is the control**:

- the same reader, same code, same timeouts detected EOF in **0.3s** on the direct path, so it
  is demonstrably capable of observing termination — `still_open` is not the reader sleeping
- `backend_at_eof=exited` on all four runs: the upstream really was dead
- 120s versus 0.3s is a **400×** separation, not a marginal timing difference

## Verdict

**BUG-123 is CONFIRMED.** With the client, the reader, the query and the turn state all held
fixed, the *only* remaining difference between a 0.3-second EOF and no EOF at all is whether
the request traversed the Next.js proxy. That is the isolation the record asked for.

### One reading of the fork rule, stated explicitly

Task 1.7's condition is "`still_open` at `:3000` + terminal at `:8000`". Read strictly as *a
terminal NDJSON event* (`done`/`error`/`clarification`), the condition is unsatisfiable by
construction: a `SIGKILL`ed process cannot emit a graceful frame, and indeed `terminal=False`
on **every** run including the direct control. Read as *the stream terminated* — i.e. the
client observed EOF and could run its terminal path — the direct arm satisfies it in 0.3s.
The second reading is the one BUG-123's own Expected field uses ("the downstream client's
response is terminated so the client can observe EOF"), and it is the only reading under which
the fork can resolve at all. The verdict is recorded on that reading.

### Bound, stated honestly

This probe establishes **no EOF within 120s**, not "indefinitely". The original 189s
observation is not contradicted and not re-confirmed; 120s was chosen to separate "prompt" from
"held open" decisively without an open-ended wait. A ≥120s hang after upstream death is already
the defect.

## Consequences

1. **Scope 38 → 39.** BUG-123 moves from `v1.1-defer` to `v1.0-fix`.
2. **D3 Branch T activates** — spec-31 task 2.4. The idle timer belongs in
   `frontend/hooks/useStreamChat.ts`, not `api.ts`: the hook owns `isStreaming` and `abort`,
   while `api.ts` returns only an `AbortController`. Hard constraint:
   `STREAM_IDLE_TIMEOUT_MS < experimental.proxyTimeout`, or the proxy cut masks the watchdog.
3. **BUG-074 Branch E alone would not have fixed the hang** — now demonstrated rather than
   predicted. Branch E adds a `sawTerminal` check *after* the read loop; on the proxied path
   that loop never exits, so the check never runs. This is precisely why the record was kept
   instead of being folded into BUG-074, and it vindicates that call.
4. The confirmed mechanism is **adjacent to, but distinct from, BUG-054/BUG-040**. Those turned
   out to be a body-size cap, not a timeout (`tests/e2e_real/README.md`). Both live in the same
   proxy layer; neither explains the other.

## Records updated

| File | Change |
|---|---|
| `bugs/BUG-123-…md` | renamed (dropped `unconfirmed-`), CONFIRMED banner, isolation result, triage → `v1.0-fix` |
| `bugs-registry.json` | title, `triage.decision`, `confirmation` block; summary counts resynced |
| `triage.md` | §3 split, §5 sequencing correction, §6 defer table, §7 open question closed |

### Count reconciliation

`triage.md` §3 counts **40** `v1.0-fix` records while spec-31 tracks **39** outstanding. Both are
right: `BUG-045`, the hunt's only BLOCKER, was already fixed on `develop` during the hunt (PR #101,
`d9107cb`) and is retained at BLOCKER severity because severity grades impact at discovery. The
registry's denormalised `v1_0_fix_count`/`v1_1_defer_count` were recomputed from the records rather
than hand-incremented, so 39/16 → 40/15 is a measured value, not an assumption.

### Deliberately not updated

`LAUNCH-DECISION.md` §3 and `SUMMARY.md` still describe this question as open. That is correct for
what they are — dated records of the 2026-05-28 decision, not living status. `LAUNCH-DECISION.md`
is also spec-31 task 9.1's target, which mandates an **appended** GO amendment and warns against a
superseding document, so editing it here would pre-empt Phase 9. Their pointers into `triage.md` §7
resolve to the closed item. **Phase 9 follow-up**: the GO amendment should note that one of the
four deferred questions was answered.

## Residual uncertainty

The probe isolates **that** the proxy is the variable. It does not establish **why** — whether
Next's `rewrites()` proxy fails to propagate upstream socket death, or holds the downstream
response open by design pending `proxyTimeout`. Task 2.4's client-side watchdog is robust to
either, which is why the fix does not wait on that answer.
