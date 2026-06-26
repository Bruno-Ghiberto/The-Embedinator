"""Multi-sample quality sweep for the 20-question golden Q&A dataset.

Single-sample sweeps produce noisy headline numbers because qwen2.5:7b's
default temperature (~0.8) introduces ±15-20pp variance per run. This harness
runs the full sweep N times serially against a target collection, emits
per-question and aggregate statistics (rate mean ± stddev, 95% CI), and
saves the full per-run trace JSON for replay/audit.

Usage:
    SWEEP_N=5 SWEEP_OUT=path/to/multi-sample.json \\
        SWEEP_COLLECTION=<uuid> \\
        python3 scripts/multi_sample_sweep.py

Defaults:
    SWEEP_N=5
    SWEEP_OUT=docs/E2E/2026-04-24-bug-hunt/multi-sample-baseline.json
    SWEEP_COLLECTION read from /tmp/bm25_collection_id.txt or the
        SWEEP_COLLECTION env var

Output schema:
    {
      "ts": ISO-8601 UTC,
      "collection_id": str,
      "n_runs": int,
      "results_per_question": [
        {
          "q_id": "Q-001",
          "category": "factoid",
          "expected_behavior": "answer",
          "runs": [{cits, declined, elapsed_s, error, answer_first_200}, ...],
          "answered_count": int,            # cits>0 AND not declined-flag
          "has_citations_count": int,       # cits>0 (less noisy than declined-flag)
          "answer_rate": float,             # answered_count / n_runs
          "mean_elapsed_s": float,
          "stddev_elapsed_s": float,
          "errored_count": int
        }
      ],
      "aggregate_per_run": [{run_idx, answered, has_cits, total, rate}, ...],
      "summary_by_category": {
        "factoid": {n_questions, n_runs, mean_rate, stddev_rate,
                    mean_has_cits_rate, stddev_has_cits_rate}
      },
      "overall": {n_questions, n_runs, mean_rate, stddev_rate,
                  mean_has_cits_rate, ci95_rate}
    }
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import statistics
import sys
import time
from pathlib import Path

import httpx
import yaml

BASE = "http://localhost:8000"
GOLDEN = Path("docs/E2E/2026-04-24-bug-hunt/golden-qa.yaml")
DEFAULT_OUT = Path("docs/E2E/2026-04-24-bug-hunt/multi-sample-baseline.json")
DEFAULT_N = 5

DECLINE_MARKERS = [
    "no tengo suficiente información",
    "no encuentro información",
    "no se encuentra",
    "no se especifica",
    "no se proporciona",
    "no puedo responder",
    "i don't have enough information",
    "i cannot find",
    "none of the provided passages",
    "the provided passages do not",
    "none were sufficiently relevant",
    "no se mencionan",
    "no menciona",
    "no proporciona información",
]


def is_declined(text: str, citation_count: int) -> bool:
    """Match the same heuristic the single-sample sweep uses for parity."""
    if citation_count == 0:
        return True
    lower = text.lower()
    return any(m in lower for m in DECLINE_MARKERS)


async def query_one(client: httpx.AsyncClient, coll_id: str, q: dict) -> dict:
    payload = {"message": q["question_es"], "collection_ids": [coll_id]}
    start = time.monotonic()
    text_parts: list[str] = []
    citation_count = 0
    error: str | None = None

    try:
        async with client.stream(
            "POST",
            f"{BASE}/api/chat",
            json=payload,
            timeout=httpx.Timeout(180.0, connect=10.0),
        ) as resp:
            if resp.status_code != 200:
                error = f"HTTP {resp.status_code}"
                async for _ in resp.aiter_lines():
                    pass
            else:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    et = evt.get("type")
                    if et == "chunk":
                        text_parts.append(evt.get("text", ""))
                    elif et == "citation":
                        citation_count = len(evt.get("citations", []))
                    elif et == "error":
                        error = evt.get("message") or evt.get("code") or "error"
    except (httpx.ReadTimeout, httpx.ReadError, httpx.ConnectError) as e:
        error = f"{type(e).__name__}: {e}"

    elapsed = time.monotonic() - start
    answer = "".join(text_parts)

    return {
        "cits": citation_count,
        "declined": is_declined(answer, citation_count) if error is None else False,
        "elapsed_s": round(elapsed, 1),
        "error": error,
        "answer_first_200": answer[:200],
    }


def stddev_safe(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return round(statistics.stdev(values), 4)


def ci95(values: list[float]) -> list[float]:
    """95% normal-approx CI. Simple z=1.96 over stddev/sqrt(n)."""
    if not values:
        return [0.0, 0.0]
    mean = statistics.mean(values)
    if len(values) < 2:
        return [round(mean, 4), round(mean, 4)]
    sem = statistics.stdev(values) / (len(values) ** 0.5)
    lo = round(max(0.0, mean - 1.96 * sem), 4)
    hi = round(min(1.0, mean + 1.96 * sem), 4)
    return [lo, hi]


async def main():
    n_runs = int(os.environ.get("SWEEP_N", DEFAULT_N))
    out_path = Path(os.environ.get("SWEEP_OUT", str(DEFAULT_OUT)))

    coll_id = os.environ.get("SWEEP_COLLECTION") or Path("/tmp/bm25_collection_id.txt").read_text().strip()
    print(f"[multi-sweep] N={n_runs}  collection={coll_id}  out={out_path}", flush=True)

    pairs = yaml.safe_load(GOLDEN.read_text())
    print(f"[multi-sweep] loaded {len(pairs)} questions × {n_runs} runs = {len(pairs) * n_runs} chats", flush=True)

    # results_per_question[q_id] = {meta, runs: [...]}
    results: dict[str, dict] = {}
    for q in pairs:
        results[q["id"]] = {
            "q_id": q["id"],
            "category": q["category"],
            "expected_behavior": q.get("expected_behavior", "answer"),
            "runs": [],
        }

    # aggregate_per_run[run_idx] = {answered, has_cits, total, rate}
    per_run: list[dict] = []

    overall_t0 = time.monotonic()
    async with httpx.AsyncClient() as client:
        for run_idx in range(n_runs):
            run_t0 = time.monotonic()
            print(f"\n=== run {run_idx + 1}/{n_runs} ===", flush=True)
            run_answered = 0
            run_has_cits = 0
            for i, q in enumerate(pairs, 1):
                r = await query_one(client, coll_id, q)
                answered = r["cits"] > 0 and not r["declined"]
                has_cits = r["cits"] > 0
                if answered:
                    run_answered += 1
                if has_cits:
                    run_has_cits += 1
                results[q["id"]]["runs"].append(r)
                print(
                    f"  [{i:>2}/{len(pairs)}] {q['id']} ({q['category']}) "
                    f"cits={r['cits']} declined={r['declined']} {r['elapsed_s']}s "
                    f"err={r['error']}",
                    flush=True,
                )
            run_elapsed = round(time.monotonic() - run_t0, 1)
            per_run.append(
                {
                    "run_idx": run_idx,
                    "answered": run_answered,
                    "has_cits": run_has_cits,
                    "total": len(pairs),
                    "rate": round(run_answered / len(pairs), 4),
                    "has_cits_rate": round(run_has_cits / len(pairs), 4),
                    "elapsed_s": run_elapsed,
                }
            )
            print(
                f"  → run {run_idx + 1} done: answered={run_answered}/{len(pairs)} "
                f"has_cits={run_has_cits}/{len(pairs)} in {run_elapsed}s",
                flush=True,
            )

    overall_elapsed = round(time.monotonic() - overall_t0, 1)

    # ----- per-question stats -----
    per_q_list = []
    for q in pairs:
        rec = results[q["id"]]
        runs = rec["runs"]
        elapsed_vals = [r["elapsed_s"] for r in runs if r["error"] is None]
        answered_count = sum(1 for r in runs if r["cits"] > 0 and not r["declined"])
        has_cits_count = sum(1 for r in runs if r["cits"] > 0)
        errored_count = sum(1 for r in runs if r["error"] is not None)

        per_q_list.append(
            {
                "q_id": rec["q_id"],
                "category": rec["category"],
                "expected_behavior": rec["expected_behavior"],
                "runs": runs,
                "answered_count": answered_count,
                "has_citations_count": has_cits_count,
                "errored_count": errored_count,
                "answer_rate": round(answered_count / n_runs, 4),
                "has_citations_rate": round(has_cits_count / n_runs, 4),
                "mean_elapsed_s": round(statistics.mean(elapsed_vals), 1) if elapsed_vals else 0.0,
                "stddev_elapsed_s": stddev_safe(elapsed_vals),
            }
        )

    # ----- per-category aggregate (rate distribution across runs) -----
    by_cat: dict[str, dict] = {}
    cats = sorted({q["category"] for q in pairs})
    for cat in cats:
        cat_qids = [q["id"] for q in pairs if q["category"] == cat]
        # Per-run rate within this category
        cat_rates_per_run = []
        cat_has_cits_per_run = []
        for run_idx in range(n_runs):
            ans = sum(
                1
                for qid in cat_qids
                if results[qid]["runs"][run_idx]["cits"] > 0 and not results[qid]["runs"][run_idx]["declined"]
            )
            has_c = sum(1 for qid in cat_qids if results[qid]["runs"][run_idx]["cits"] > 0)
            cat_rates_per_run.append(ans / len(cat_qids))
            cat_has_cits_per_run.append(has_c / len(cat_qids))
        by_cat[cat] = {
            "n_questions": len(cat_qids),
            "n_runs": n_runs,
            "mean_rate": round(statistics.mean(cat_rates_per_run), 4),
            "stddev_rate": stddev_safe(cat_rates_per_run),
            "mean_has_cits_rate": round(statistics.mean(cat_has_cits_per_run), 4),
            "stddev_has_cits_rate": stddev_safe(cat_has_cits_per_run),
            "ci95_rate": ci95(cat_rates_per_run),
        }

    # ----- overall aggregate -----
    overall_rates = [p["rate"] for p in per_run]
    overall_has_cits = [p["has_cits_rate"] for p in per_run]
    overall = {
        "n_questions": len(pairs),
        "n_runs": n_runs,
        "mean_rate": round(statistics.mean(overall_rates), 4),
        "stddev_rate": stddev_safe(overall_rates),
        "ci95_rate": ci95(overall_rates),
        "mean_has_cits_rate": round(statistics.mean(overall_has_cits), 4),
        "stddev_has_cits_rate": stddev_safe(overall_has_cits),
        "elapsed_s_total": overall_elapsed,
    }

    output = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "collection_id": coll_id,
        "n_runs": n_runs,
        "results_per_question": per_q_list,
        "aggregate_per_run": per_run,
        "summary_by_category": by_cat,
        "overall": overall,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")

    print(f"\n[saved] {out_path}", flush=True)
    print("\n=== Multi-sample summary ===")
    print(
        f"  Overall:       answered={overall['mean_rate']:.1%} ± {overall['stddev_rate']:.1%}  "
        f"(95% CI {overall['ci95_rate'][0]:.1%}-{overall['ci95_rate'][1]:.1%})"
    )
    print(f"                 has-cits={overall['mean_has_cits_rate']:.1%}")
    print(
        f"                 elapsed={overall['elapsed_s_total']}s "
        f"({overall['elapsed_s_total'] / n_runs / 60:.1f} min/run avg)"
    )
    print()
    for cat in cats:
        s = by_cat[cat]
        print(
            f"  {cat:<14} answered={s['mean_rate']:.1%} ± {s['stddev_rate']:.1%}  "
            f"has-cits={s['mean_has_cits_rate']:.1%}  "
            f"(95% CI {s['ci95_rate'][0]:.1%}-{s['ci95_rate'][1]:.1%})"
        )


if __name__ == "__main__":
    asyncio.run(main())
