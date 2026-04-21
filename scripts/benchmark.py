#!/usr/bin/env python3
"""Benchmark harness for The Embedinator — spec-26 FR-002.

Measures cold-start and warm-state latency across factoid and analytical
query classes. Supports repeat-run variance (NFR-003) and concurrent load
(SC-006). Emits a JSON result file consumable by Gate 2/3/4 checks.

Usage (smoke run):
    python scripts/benchmark.py \\
        --factoid-n 5 --analytical-n 2 --priming-queries 1 \\
        --output /tmp/bench-smoke.json \\
        --base-url http://localhost:8000 \\
        --collection-id "$(cat /tmp/spec26-collection-id.txt)"

Usage (pre-fix baseline):
    SHA=$(git rev-parse --short HEAD)
    python scripts/benchmark.py \\
        --factoid-n 30 --analytical-n 10 --priming-queries 1 --repeat 3 \\
        --output "docs/benchmarks/${SHA}-pre-spec26.json" \\
        --base-url http://localhost:8000 \\
        --collection-id "$(cat /tmp/spec26-collection-id.txt)"

Usage (concurrency SC-006):
    python scripts/benchmark.py \\
        --concurrent 5 --factoid-n 5 --priming-queries 1 \\
        --output /tmp/conc.json \\
        --base-url http://localhost:8000 \\
        --collection-id "$(cat /tmp/spec26-collection-id.txt)"
"""

import argparse
import asyncio
import hashlib
import json
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
import httpx


# ---------------------------------------------------------------------------
# Query corpus — deterministic, repeatable (30 factoid + 10 analytical)
# Generic enough to work against any knowledge-base corpus.
# ---------------------------------------------------------------------------

FACTOID_QUERIES = [
    "What is this document about?",
    "What topics are covered in this collection?",
    "What are the key concepts in this document?",
    "List the main sections of the document.",
    "What is the primary subject matter here?",
    "Summarize the first paragraph of the document.",
    "What definitions are provided in this document?",
    "What examples are given in this document?",
    "What technical terms appear in this document?",
    "What methods or approaches are described?",
    "Are there any numbered lists in this document?",
    "What is the purpose of this document?",
    "Does the document mention any tools or technologies?",
    "What outcomes or results are discussed?",
    "Are there any warnings or caveats mentioned?",
    "What is the structure of this document?",
    "Are there any references or citations in this document?",
    "What requirements or constraints are mentioned?",
    "What processes or workflows are described?",
    "What components are listed in this document?",
    "Are there any configuration options described?",
    "What is the scope of this document?",
    "What types of data are discussed?",
    "What is the recommended approach according to this document?",
    "Are there any performance considerations mentioned?",
    "What errors or problems are addressed?",
    "How is the system initialized according to this document?",
    "What interfaces or APIs are described?",
    "What is the main conclusion of this document?",
    "Summarize the document in two sentences.",
]

ANALYTICAL_QUERIES = [
    (
        "Compare and contrast the different approaches described in this document "
        "and explain the tradeoffs between them."
    ),
    (
        "How do the concepts in this document relate to each other, "
        "and what is the overall design philosophy being expressed?"
    ),
    (
        "Analyze the strengths and limitations of the methods described "
        "in this document from a practical implementation perspective."
    ),
    (
        "What are the key dependencies and relationships between the components "
        "described here, and how do they interact?"
    ),
    (
        "How would you implement the main idea described in this document "
        "in a real-world production scenario? What would be the main challenges?"
    ),
    ("What are the most important decisions described in this document, and what are their long-term implications?"),
    ("Synthesize the main themes across all sections of this document into a coherent narrative."),
    (
        "What problems does this document solve, and what alternative solutions "
        "could have been chosen instead? Why might they have been rejected?"
    ),
    (
        "Evaluate the completeness of the documentation — what is missing "
        "that would be needed for a full implementation?"
    ),
    (
        "Describe the end-to-end workflow implied by the content of this document, "
        "from initial setup through operation to maintenance."
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def wait_for_backend(base_url: str, timeout: int = 120) -> None:
    """Poll /api/health until 200 or raise on timeout.

    Catches all httpx errors (ConnectError, TimeoutException, RemoteProtocolError,
    etc.) so restarts that momentarily return broken connections don't abort the wait.
    """
    deadline = time.monotonic() + timeout
    last_err = None
    while time.monotonic() < deadline:
        try:
            # Create a fresh client on every attempt — avoids reusing a
            # connection that the restarting container has already torn down.
            async with httpx.AsyncClient(base_url=base_url) as client:
                r = await client.get("/api/health", timeout=5.0)
                if r.status_code == 200:
                    return
        except Exception as exc:
            last_err = exc
        await asyncio.sleep(1)
    raise RuntimeError(f"Backend at {base_url} did not become healthy within {timeout}s (last error: {last_err})")


async def get_manifest_fields(base_url: str, collection_id: str) -> dict:
    """Fetch model name, commit SHA, and compute corpus fingerprint."""
    async with httpx.AsyncClient(base_url=base_url) as client:
        # LLM model from /api/settings
        model = "unknown"
        try:
            r = await client.get("/api/settings", timeout=10.0)
            r.raise_for_status()
            model = r.json().get("default_llm_model", "unknown")
        except Exception:
            pass

        # Document count for fingerprint
        doc_count = 0
        try:
            r = await client.get("/api/collections", timeout=10.0)
            r.raise_for_status()
            for coll in r.json().get("collections", []):
                if coll["id"] == collection_id:
                    doc_count = coll.get("document_count", 0)
                    break
        except Exception:
            pass

    fingerprint = hashlib.md5(f"{collection_id}:{doc_count}".encode()).hexdigest()[:12]

    # Git commit SHA
    commit_sha = "unknown"
    try:
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        pass

    return {
        "model": model,
        "corpus_fingerprint": fingerprint,
        "commit_sha": commit_sha,
    }


async def run_single_query(
    client: httpx.AsyncClient,
    query: str,
    collection_id: str,
) -> dict:
    """
    Fire one chat query; stream until 'done' or 'error'.

    Returns:
        wall_ms   — wall-clock ms from POST send to 'done' frame receipt
        trace_id  — from the 'done' event (None on error)
        error     — error code/type string (None on success)
    """
    body = {
        "message": query,
        "collection_ids": [collection_id],
        "session_id": str(uuid.uuid4()),  # fresh session → no history contamination
    }
    t0 = time.monotonic()
    trace_id = None
    error = None

    try:
        async with client.stream(
            "POST",
            "/api/chat",
            json=body,
            timeout=httpx.Timeout(connect=10.0, read=360.0, write=10.0, pool=10.0),
        ) as response:
            response.raise_for_status()
            async for raw_line in response.aiter_lines():
                if not raw_line.strip():
                    continue
                try:
                    evt = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                evt_type = evt.get("type")
                if evt_type == "done":
                    trace_id = evt.get("trace_id")
                    break
                elif evt_type == "error":
                    error = evt.get("code") or evt.get("message", "UNKNOWN_ERROR")
                    break
    except httpx.HTTPStatusError as exc:
        error = f"HTTPStatusError:{exc.response.status_code}"
    except httpx.ReadTimeout:
        error = "ReadTimeout"
    except Exception as exc:
        error = type(exc).__name__

    wall_ms = int((time.monotonic() - t0) * 1000)
    return {"wall_ms": wall_ms, "trace_id": trace_id, "error": error}


async def read_stage_timings(db_path: str, trace_id: str) -> dict[str, float]:
    """
    Read stage_timings_json for a trace row from SQLite (host-side read in WAL mode).

    The trace is written BEFORE the 'done' event is emitted by chat.py, but
    aiosqlite may need a brief moment for WAL flush. Retries up to 500 ms.

    Actual DB shape: {"stage_name": {"duration_ms": float}, ...}
    Returns flat dict: {stage_name: duration_ms}
    """
    for _ in range(5):
        await asyncio.sleep(0.1)
        try:
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT stage_timings_json FROM query_traces WHERE id = ?",
                    (trace_id,),
                )
                row = await cursor.fetchone()
                if row and row["stage_timings_json"]:
                    raw = json.loads(row["stage_timings_json"])
                    result: dict[str, float] = {}
                    for stage, val in raw.items():
                        if isinstance(val, dict):
                            result[stage] = float(val.get("duration_ms", 0.0))
                        else:
                            result[stage] = float(val)
                    return result
        except Exception:
            pass
    return {}


def _percentile(data: list[float], p: int) -> float:
    """Linear-interpolation percentile (matches numpy default)."""
    if not data:
        return 0.0
    n = len(data)
    if n == 1:
        return data[0]
    sorted_data = sorted(data)
    idx = (p / 100.0) * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    return sorted_data[lo] + (idx - lo) * (sorted_data[hi] - sorted_data[lo])


# ---------------------------------------------------------------------------
# Measurement pass (priming + measured queries)
# ---------------------------------------------------------------------------


async def run_measurement_pass(
    base_url: str,
    collection_id: str,
    factoid_n: int,
    analytical_n: int,
    priming_queries: int,
    concurrent: int,
    db_path: str,
    run_label: str = "",
) -> dict:
    """
    Execute one full measurement pass: priming phase + measurement phase.

    Returns:
        cold_start_ms          — wall-clock of first priming query (None if priming=0)
        factoid_wall_times     — list of measured factoid wall-clock ms
        analytical_wall_times  — list of measured analytical wall-clock ms
        all_stage_timings      — list of {stage: ms} dicts from DB
        errors                 — list of error dicts
    """
    cold_start_ms: int | None = None
    factoid_wall_times: list[float] = []
    analytical_wall_times: list[float] = []
    all_stage_timings: list[dict[str, float]] = []
    errors: list[dict] = []

    # httpx client with generous pool for concurrency
    limits = httpx.Limits(max_connections=max(concurrent + 2, 10))
    async with httpx.AsyncClient(base_url=base_url, limits=limits) as client:
        # ── Priming phase ──────────────────────────────────────────────────
        for i in range(priming_queries):
            query = FACTOID_QUERIES[i % len(FACTOID_QUERIES)]
            label = f"[{run_label}priming {i + 1}/{priming_queries}]"
            print(f"  {label} ...", end=" ", flush=True)
            res = await run_single_query(client, query, collection_id)
            print(f"{res['wall_ms']}ms", flush=True)
            if i == 0:
                cold_start_ms = res["wall_ms"]
            if res["error"]:
                print(f"  {label} WARNING: {res['error']}", flush=True)

        # ── Measurement phase ──────────────────────────────────────────────
        # Build ordered query list (factoid first, then analytical)
        measured: list[tuple[str, str]] = []
        for i in range(factoid_n):
            measured.append(("factoid", FACTOID_QUERIES[i % len(FACTOID_QUERIES)]))
        for i in range(analytical_n):
            measured.append(("analytical", ANALYTICAL_QUERIES[i % len(ANALYTICAL_QUERIES)]))

        if concurrent <= 1:
            # Sequential
            total = len(measured)
            for idx, (qtype, query) in enumerate(measured):
                label = f"[{run_label}{qtype} {idx + 1}/{total}]"
                print(f"  {label} ...", end=" ", flush=True)
                res = await run_single_query(client, query, collection_id)
                print(f"{res['wall_ms']}ms", flush=True)
                if res["error"]:
                    errors.append(
                        {
                            "type": res["error"],
                            "query_type": qtype,
                            "query_index": idx,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                else:
                    if qtype == "factoid":
                        factoid_wall_times.append(res["wall_ms"])
                    else:
                        analytical_wall_times.append(res["wall_ms"])
                    if res["trace_id"]:
                        timings = await read_stage_timings(db_path, res["trace_id"])
                        if timings:
                            all_stage_timings.append(timings)
        else:
            # Concurrent (SC-006): fire all queries simultaneously up to `concurrent` limit
            semaphore = asyncio.Semaphore(concurrent)

            async def bounded_query(idx: int, qtype: str, query: str) -> dict:
                async with semaphore:
                    res = await run_single_query(client, query, collection_id)
                    return {"idx": idx, "qtype": qtype, **res}

            tasks = [asyncio.create_task(bounded_query(i, qt, q)) for i, (qt, q) in enumerate(measured)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    errors.append(
                        {
                            "type": type(res).__name__,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    continue
                if res.get("error"):
                    err_type = res["error"]
                    # Normalise circuit breaker variants for SC-006 checking
                    if "CIRCUIT_OPEN" in str(err_type).upper():
                        err_type = "CircuitOpenError"
                    errors.append(
                        {
                            "type": err_type,
                            "query_type": res.get("qtype"),
                            "query_index": res.get("idx"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                else:
                    qtype = res.get("qtype", "factoid")
                    if qtype == "factoid":
                        factoid_wall_times.append(res["wall_ms"])
                    else:
                        analytical_wall_times.append(res["wall_ms"])
                    if res.get("trace_id"):
                        timings = await read_stage_timings(db_path, res["trace_id"])
                        if timings:
                            all_stage_timings.append(timings)

    return {
        "cold_start_ms": cold_start_ms,
        "factoid_wall_times": factoid_wall_times,
        "analytical_wall_times": analytical_wall_times,
        "all_stage_timings": all_stage_timings,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Repeat-run backend restart (T040)
# ---------------------------------------------------------------------------


async def restart_backend_for_cold_start(base_url: str) -> None:
    """
    Restart only the backend container (NOT Qdrant) so the next run starts
    with a cold LLM VRAM state. Waits for /api/health before returning.

    Decision 3 (research.md): backend-only restart; Qdrant stays up.
    """
    print("  [restart] docker compose restart backend ...", end=" ", flush=True)
    subprocess.run(
        ["docker", "compose", "restart", "backend"],
        check=True,
    )
    # Give the container a moment to fully stop before we start health-checking
    # Backend needs ~90-180s to restart (cross-encoder model load + HuggingFace retries)
    await asyncio.sleep(5)
    await wait_for_backend(base_url, timeout=300)
    print("healthy", flush=True)


# ---------------------------------------------------------------------------
# Main benchmark orchestration
# ---------------------------------------------------------------------------


async def run_benchmark(args: argparse.Namespace) -> None:
    base_url = args.base_url
    collection_id = args.collection_id
    # DB is at data/embedinator.db relative to repo root (two levels up from scripts/)
    db_path = str(Path(__file__).parent.parent / "data" / "embedinator.db")

    print("=" * 60)
    print("Benchmark Harness — The Embedinator (spec-26 FR-002)")
    print("=" * 60)
    print(f"  base_url        : {base_url}")
    print(f"  collection_id   : {collection_id}")
    print(f"  factoid_n       : {args.factoid_n}")
    print(f"  analytical_n    : {args.analytical_n}")
    print(f"  priming_queries : {args.priming_queries}")
    print(f"  repeat          : {args.repeat}")
    print(f"  concurrent      : {args.concurrent}")
    print(f"  output          : {args.output}")
    print()

    if args.priming_queries == 0:
        print(
            "  NOTE: --priming-queries 0 disables warm-up. "
            "cold_start_ms will be null and warm-state stats are invalid.",
            flush=True,
        )

    # Preflight: backend must be reachable before we start
    print("[preflight] waiting for backend health ...", end=" ", flush=True)
    await wait_for_backend(base_url)
    print("OK", flush=True)

    manifest_fields = await get_manifest_fields(base_url, collection_id)
    print(
        f"[manifest]  model={manifest_fields['model']}  "
        f"sha={manifest_fields['commit_sha']}  "
        f"fingerprint={manifest_fields['corpus_fingerprint']}",
        flush=True,
    )

    all_run_results: list[dict] = []

    for run_idx in range(args.repeat):
        if run_idx > 0:
            # Fresh cold-start for each subsequent repeat (NFR-003 protocol)
            await restart_backend_for_cold_start(base_url)

        print(f"\n[run {run_idx + 1}/{args.repeat}]", flush=True)
        result = await run_measurement_pass(
            base_url=base_url,
            collection_id=collection_id,
            factoid_n=args.factoid_n,
            analytical_n=args.analytical_n,
            priming_queries=args.priming_queries,
            concurrent=args.concurrent,
            db_path=db_path,
            run_label=f"r{run_idx + 1}|",
        )
        all_run_results.append(result)

        f_p50 = _percentile(result["factoid_wall_times"], 50)
        a_p50 = _percentile(result["analytical_wall_times"], 50)
        print(
            f"  summary: cold={result['cold_start_ms']}ms  "
            f"factoid_p50={f_p50:.0f}ms  analytical_p50={a_p50:.0f}ms  "
            f"errors={len(result['errors'])}",
            flush=True,
        )

    # ── Aggregation ───────────────────────────────────────────────────────
    all_factoid: list[float] = []
    all_analytical: list[float] = []
    all_stage_timings: list[dict[str, float]] = []
    all_errors: list[dict] = []
    per_run_factoid_p50: list[float] = []

    for r in all_run_results:
        all_factoid.extend(r["factoid_wall_times"])
        all_analytical.extend(r["analytical_wall_times"])
        all_stage_timings.extend(r["all_stage_timings"])
        all_errors.extend(r["errors"])
        if r["factoid_wall_times"]:
            per_run_factoid_p50.append(_percentile(r["factoid_wall_times"], 50))

    # Variance CV: stdev(per-run factoid p50) / mean(per-run factoid p50)
    # Meaningful only when repeat >= 2; 0.0 for single run.
    if len(per_run_factoid_p50) >= 2:
        mean_p50 = statistics.mean(per_run_factoid_p50)
        stdev_p50 = statistics.stdev(per_run_factoid_p50)
        variance_cv = stdev_p50 / mean_p50 if mean_p50 > 0 else 0.0
    else:
        variance_cv = 0.0

    # Stage timings p50 — emit whatever keys the DB actually contains
    stage_keys: set[str] = set()
    for t in all_stage_timings:
        stage_keys.update(t.keys())
    stage_timings_p50: dict[str, float] = {}
    for key in sorted(stage_keys):
        vals = [t[key] for t in all_stage_timings if key in t]
        if vals:
            stage_timings_p50[key] = round(_percentile(vals, 50), 1)

    # Warm-state percentiles (all repeat-runs combined)
    def _stats(vals: list[float]) -> tuple[int, int, int]:
        if not vals:
            return 0, 0, 0
        return (
            int(_percentile(vals, 50)),
            int(_percentile(vals, 90)),
            int(_percentile(vals, 99)),
        )

    f_p50, f_p90, f_p99 = _stats(all_factoid)
    a_p50, a_p90, a_p99 = _stats(all_analytical)

    # Cold start from first run's first priming query
    cold_start_ms: int | None = all_run_results[0].get("cold_start_ms")

    cold_vs_warm_ratio: float = 0.0
    if cold_start_ms is not None and f_p50 > 0:
        cold_vs_warm_ratio = round(cold_start_ms / f_p50, 2)

    done_count = len(all_factoid) + len(all_analytical)

    # ── Build output JSON ─────────────────────────────────────────────────
    output = {
        "manifest": {
            "commit_sha": manifest_fields["commit_sha"],
            "corpus_fingerprint": manifest_fields["corpus_fingerprint"],
            "model": manifest_fields["model"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "factoid_n": args.factoid_n,
            "analytical_n": args.analytical_n,
            "priming_queries": args.priming_queries,
            "concurrent": args.concurrent,
            "repeat": args.repeat,
        },
        "cold_start_ms": cold_start_ms,
        "cold_vs_warm_ratio": cold_vs_warm_ratio,
        "variance_cv": round(variance_cv, 4),
        "warm_state_p50": {"factoid_ms": f_p50, "analytical_ms": a_p50},
        "warm_state_p90": {"factoid_ms": f_p90, "analytical_ms": a_p90},
        "warm_state_p99": {"factoid_ms": f_p99, "analytical_ms": a_p99},
        "overall_p50": {"factoid_ms": f_p50, "analytical_ms": a_p50},
        "stage_timings_p50": stage_timings_p50,
        "completions": {"done_count": done_count, "error_count": len(all_errors)},
        "errors": all_errors,
    }

    # ── Write output ──────────────────────────────────────────────────────
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n")

    print()
    print("=" * 60)
    print(f"[done] {out_path}")
    print(f"  warm_state_p50.factoid_ms    = {f_p50} ms")
    print(f"  warm_state_p50.analytical_ms = {a_p50} ms")
    print(f"  cold_start_ms                = {cold_start_ms} ms")
    print(
        f"  variance_cv                  = {variance_cv:.4f}"
        + ("  ← EXCEEDS NFR-003 (0.15)" if variance_cv > 0.15 else "")
    )
    print(f"  stage_timings keys           : {list(stage_timings_p50.keys())}")
    print(f"  completions                  : {done_count} done / {len(all_errors)} errors")

    if variance_cv > 0.15:
        print()
        print(
            "  WARNING: variance_cv exceeds NFR-003 ceiling (0.15). "
            "Check for thermal throttling, competing GPU workloads, or "
            "Ollama model swaps between runs."
        )

    # Plausibility guard — flag measurement anomalies to the caller
    if f_p50 > 0 and f_p50 < 500:
        print(
            "  WARNING: factoid warm p50 < 500ms — likely measurement error "
            "(priming query captured as warm, or stack not running correctly)."
        )
    if f_p50 > 300_000:
        print("  WARNING: factoid warm p50 > 300s — stack may be broken or Ollama model not loaded.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark harness for The Embedinator — spec-26 FR-002",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--factoid-n",
        type=int,
        default=30,
        help="Number of factoid queries per run (default: 30)",
    )
    parser.add_argument(
        "--analytical-n",
        type=int,
        default=10,
        help="Number of analytical queries per run (default: 10)",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=1,
        help="Concurrent query count — use 5 for SC-006 validation (default: 1)",
    )
    parser.add_argument(
        "--priming-queries",
        type=int,
        default=1,
        help=(
            "Warm-up queries excluded from warm-state stats (default: 1). "
            "Set 0 only for debugging — invalidates warm-state statistics."
        ),
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help=(
            "Repeat full harness N times for NFR-003 variance measurement. "
            "Each repeat restarts the backend container for a fresh cold-start (default: 1)."
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to JSON output file (parent directory is created if absent)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8000",
        help="Backend API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--collection-id",
        type=str,
        required=True,
        help="Collection ID to benchmark against (use /tmp/spec26-collection-id.txt)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(run_benchmark(args))
    except KeyboardInterrupt:
        print("\n[aborted] Benchmark interrupted by user", flush=True)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[error] Benchmark failed: {exc}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
