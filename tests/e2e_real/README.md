# `tests/e2e_real/` — the real-socket harness

## Why this exists

`tests/e2e/` is **not** end-to-end. `tests/e2e/test_chat_e2e.py:80` drives the app through
`httpx.ASGITransport` — in-process ASGI, no socket, no proxy, no process boundary. Every bug
that lives in one of those three places is invisible to it.

That matters because spec-31's GO condition #1 forbids re-verifying the round-1 CRITICALs
using the instrument that missed them. This directory is the replacement: real processes,
real sockets, real HTTP.

| Component | How it runs |
|---|---|
| Backend | its own `uvicorn` subprocess, ephemeral port, real socket |
| Ollama | a deterministic in-repo stub (`fake_ollama.py`), 6 failure-injection modes |
| Qdrant | the real container, started by `scripts/run-e2e-live.sh` |
| Next | a real `next dev` or `standalone` server (`next_proxy.py`, `standalone_proxy.py`) |

## Running it

The suite is **opt-in**. Every test carrying `@pytest.mark.require_server` skips unless
`E2E_REAL=1` is set, so a normal run is unaffected.

```bash
# brings up Qdrant only, verifies it, then hands off to the sanctioned runner
zsh scripts/run-e2e-live.sh
```

Note `run-e2e-live.sh` is **bash** — it uses `BASH_SOURCE[0]`, so invoking it with `zsh` leaves
`REPO_ROOT` empty and it fails with a misleading `//frontend/node_modules is missing`.
`run-tests-external.sh`, by contrast, *is* zsh. They differ; use each with its own shell.

Never invoke `pytest` directly — see the testing policy in `CLAUDE.md`. Use
`zsh scripts/run-tests-external.sh -n s31-b{N}-{bug}-{red|green} <target>`.

### Baseline

`s31-baseline`, 2026-08-04, target `tests/`:

```
1534 passed, 34 skipped, 48 xfailed, 16 xpassed in 47.33s   (coverage 85%)
```

**Zero failures.** Any earlier figure — the "39 pre-existing failures", or
`baseline.summary`'s `75 failed, 1246 passed` — is obsolete and archived under
`Docs/Tests/archive-pre-spec-31/`. Gate every run against zero.

The `16 xpassed` are the obsolete blanket-xfail markers catalogued in
`docs/Project_blueprints/blanket-xfail-audit.md`.

### Two things a run will do to your working tree

- **`frontend/next-env.d.ts` gets rewritten** by any fixture that starts a Next server
  (`./.next/types/…` ⇄ `./.next/dev/types/…`, depending on dev vs standalone). It is generated
  and must not be edited, but it *will* show as modified afterwards. Restore it with
  `git checkout -- frontend/next-env.d.ts` before freezing a review candidate, or the stray diff
  invalidates the snapshot.
- **`Docs/Tests/` fills with run evidence.** It is gitignored recursively, including archive
  subdirectories, so it never reaches a commit.

---

## SCOPE BOUNDARY — read this before citing a green run as evidence

This harness covers **the backend class of defect**. It does not cover three other classes,
and a green suite is not evidence for any of them.

### 1. It does not gate the proxy / upload class

BUG-054 and BUG-040 are **one defect**, and it is a **size cap**, not a timeout.

Measured on the live Docker stack, 2026-08-04:

| Size | Path | Duration | Result |
|---|---|---|---|
| 12.6 MB | via proxy `:3000` | 63.5s | FAIL — client 500, backend logged `status=400` |
| 12.6 MB | direct `:8000` | 41.0s | 202 |
| **8.0 MB** | **via proxy `:3000`** | **39.0s** | **202** |

The third row is the discriminator: a **39-second proxied request succeeded**. There is no
~30s idle timeout. The trigger is Next's `proxyClientMaxBodySize` 10 MB default; the original
`30028 ms` was simply how long a 26.1 MB transfer took before hitting the cap.

The earlier exit gate asserted a 30s proxy cut. It was deleted rather than adjusted, because a
gate built on a refuted premise is worse than no gate.

- **Regression cover**: task 2.2 — *import* `next.config.ts` and assert
  `proxyClientMaxBodySize === 104_857_600`. Never regex the file.
- **Behavioural evidence**: the Docker stack, plus the Phase 8.2 operator transcript.

### 2. It does not gate the client-side stream class

BUG-074 is **purely client-side**. The backend does emit a terminal event under
`die_midstream` — verified, and locked here by
`test_wire_contract.py::test_backend_terminates_a_stream_whose_upstream_died`. The defect is in
`frontend/lib/api.ts:157-208`, whose `while (true)` loop breaks on `done` and calls nothing.

No pytest can exercise that. **BUG-074's RED test belongs in the frontend vitest suite.**

### 3. It does not gate GC-2 or GC-6 — these are operator gates

> **A green suite is never evidence for GC-2 or GC-6.**

Both require a human-run destructive event (`docker compose down -v`, model unloaded, first
chat issued at `:3000` and never `:8000`) with the transcript and first-byte gap captured.
No agent holds the permission, and no agent can close them. See tasks 8.1–8.3.

A batch can be 100% green and spec-31 still cannot close.

### Known harness artifact — host loopback

Proxied requests stall inside the **backend**, between `chat.py:148` and `:192`, before the
graph runs. This does **not** occur on Docker. It is a harness defect, not a product one, and
it is the reason the proxy fixtures are not the instrument for the proxy class. Do not report
it as a product bug.

Related, and worth fixing on its own: `_chat_semaphore` is acquired *after* the `session` frame
is emitted (`chat.py:31/148/192`), which makes a wedged turn indistinguishable from a starting
one on the wire.

---

## What the harness DOES gate

`test_wire_contract.py` holds the contract this harness owns end to end:

> A backend stream that ends must say how it ended, and a backend stream that cannot end must
> be terminated by the backend itself.

| Test | Expected today | Role |
|---|---|---|
| `test_backend_terminates_a_stream_whose_upstream_died` | **green** | regression lock — the backend half of BUG-074 already holds and must keep holding |
| `test_backend_enforces_an_in_flight_llm_deadline` | **RED** | BUG-088 (task 2.7) — Batch 0's exit gate |
| `test_stall_gate_outlived_the_deadline_it_asserts` | green | guards the gate above against measuring the reader's patience |

### The method rule, kept deliberately

Every bug-reproduction RED test needs a **companion assertion that the failure came from the
system under test, not the instrument**.

This is not a style preference. On the first exit-gate run, two tests were red — and the
companion assertion revealed both were measuring nothing but the reader's own 90s timeout.
Without it, Batch 0 would have closed on a reproduction that proved nothing.

---

## Fixtures

| Fixture | Scope | Notes |
|---|---|---|
| `fake_ollama` | session | modes: `normal`, `always_ambiguous`, `stall_forever`, `stall_after_first_chunk`, `slow_first_byte(n)`, `die_midstream`. Reset around every test. |
| `backend_server` | session | uvicorn on an ephemeral port; readiness on `/api/health/live` **only** |
| `spawn_backend` | function | factory, for tests needing their own instance |
| `backend_on_baked_port` | session | fixed port — required only by `standalone_proxy` |
| `next_proxy` | session | real `next dev` |
| `standalone_proxy` | session | Next `standalone`, the mode Docker runs |

### Two constraints that are easy to rediscover the hard way

- **`BACKEND_URL` is baked at BUILD time** into `routes-manifest.json`, `required-server-files.json`
  and `server.js`. Setting it when the server starts does nothing — `frontend/Dockerfile:14`
  already treats it as an `ARG` for exactly this reason. That is why `backend_on_baked_port`
  exists and why it fails loudly instead of skipping.
- **Next 16's dev lock is per-DIRECTORY, not per-port.** A second `next dev` on the same folder
  refuses to start however free the requested port is. Reserving a port is necessary and not
  sufficient; `_find_foreign_next_dev` detects the collision and reports the PID.

Readiness is checked on `/api/health/live` and never `/api/health` — `backend/api/health.py:23`
holds a `_first_probe` module global that returns `starting` without probing on the first call
and burns the flag. For the proxy fixtures readiness goes to `GET /healthz`, never `/api/*`,
which would traverse the proxy under test.
