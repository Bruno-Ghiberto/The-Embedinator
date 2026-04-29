"""RAGAS quality baseline evaluation — spec-28 US4.

Single async test that:
  1. Iterates over the golden Q&A dataset.
  2. Issues each answerable question to the live backend chat endpoint (NDJSON stream).
  3. Collects answer text, retrieved contexts (from citation events), and reference answers.
  4. Evaluates with RAGAS (ContextPrecision, ContextRecall, AnswerRelevancy, Faithfulness).
  5. Writes per-category and overall scores to quality-metrics.md per data-model.md §4.

Design constraints:
- All ragas / datasets imports are LAZY (inside the test body) so the module can be
  imported without [quality] extras installed (import smoke check must pass).
- The test is NEVER run inside Claude Code — only via the external runner:
    zsh scripts/run-tests-external.sh -n spec28-ragas tests/quality/test_ragas_baseline.py
- If a single pair errors, it is skipped with a note in quality-metrics.md §Known limitations.
- out-of-scope and ambiguous pairs (authored_by: user) are evaluated separately:
  the expected answer is a decline / disambiguation, not a factual answer.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio

# SESSION_DIR is imported from conftest via fixtures, but we need it here for the
# output path. Re-derive it using the same hard-coded constant.
_SESSION_DIR = Path("docs/E2E/2026-04-24-bug-hunt")
_QUALITY_METRICS_PATH = _SESSION_DIR / "quality-metrics.md"

# Metric score floor for "Failure inspection" section.
_FLOOR_RETRIEVAL = 0.3
_FLOOR_ANSWER = 0.4

# NDJSON event types from backend/api/chat.py.
_CHUNK_EVENT = "chunk"
_CITATION_EVENT = "citation"
_ERROR_EVENT = "error"
_DONE_EVENT = "done"

# Categories that should produce a direct answer (run through RAGAS scoring).
_ANSWERABLE_CATEGORIES = frozenset({"factoid", "analytical", "follow-up"})

# Categories with special handling.
_DECLINE_CATEGORIES = frozenset({"out-of-scope"})
_DISAMBIGUATE_CATEGORIES = frozenset({"ambiguous"})

# Decline phrase expected in out-of-scope answers (H4 hypothesis).
_DECLINE_PHRASES = [
    "no está en los documentos",
    "no se encuentra en los documentos",
    "no tengo información",
    "fuera del alcance",
    "no está disponible",
]


# ---------------------------------------------------------------------------
# NDJSON stream parsing
# ---------------------------------------------------------------------------


async def _stream_chat(
    client: httpx.AsyncClient,
    question: str,
    session_id: str,
) -> tuple[str, list[str]]:
    """Issue one question to the backend and collect the streaming response.

    Returns:
        answer: accumulated text from chunk events.
        contexts: list of retrieved passage texts from citation events.

    On error event, raises RuntimeError with the error payload.
    """
    request_body = {
        "message": question,
        "session_id": session_id,
        "collection_ids": [],  # use all available collections
    }

    answer_parts: list[str] = []
    contexts: list[str] = []

    async with client.stream(
        "POST",
        "/api/chat",
        json=request_body,
    ) as response:
        response.raise_for_status()
        async for raw_line in response.aiter_lines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")

            if event_type == _CHUNK_EVENT:
                text = event.get("text", "")
                if text:
                    answer_parts.append(text)

            elif event_type == _CITATION_EVENT:
                for citation in event.get("citations", []):
                    # Each citation is a dict-dumped RetrievedChunk with a "text" field.
                    ctx_text = citation.get("text", "").strip()
                    if ctx_text:
                        contexts.append(ctx_text)

            elif event_type == _ERROR_EVENT:
                raise RuntimeError(f"Backend error: {json.dumps(event)}")

            # session / status / meta_reasoning / confidence / groundedness / done
            # events are informational; no action needed for RAGAS evaluation.

    return "".join(answer_parts), contexts


# ---------------------------------------------------------------------------
# quality-metrics.md writer
# ---------------------------------------------------------------------------


def _write_quality_metrics(
    *,
    session_id: str,
    category_scores: dict[str, dict[str, float | str]],
    hypotheses: dict[str, str],
    failure_inspection: list[dict[str, str]],
    known_limitations: list[str],
    judge_label: str,
    git_sha: str,
    run_duration_s: float,
    pair_counts: dict[str, int],
) -> None:
    """Write quality-metrics.md per data-model.md §4 schema.

    Leaves hypothesis evidence as placeholders when not yet confirmed/refuted —
    A6 (Wave 3) will stamp CONFIRMED/REFUTED after the run.
    """
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    metrics_order = ["context_precision", "context_recall", "answer_relevancy", "faithfulness"]
    header_labels = {
        "context_precision": "Retrieval precision",
        "context_recall": "Context recall",
        "answer_relevancy": "Answer relevance",
        "faithfulness": "Citation faithfulness",
    }

    # --- Per-category table ---
    category_display = [
        ("factoid", "Factoid"),
        ("analytical", "Analytical"),
        ("follow-up", "Follow-up"),
        ("out-of-scope", "Out-of-scope"),
        ("ambiguous", "Ambiguous"),
    ]

    col_w = 23
    header_row = "| Category     | Pairs | " + " | ".join(f"{header_labels[m]:<{col_w}}" for m in metrics_order) + " |"
    sep_row = "|:-------------|:-----:|" + ":".join(["-" * (col_w + 2)] * len(metrics_order)) + ":|"

    table_rows: list[str] = []
    overall_scores: dict[str, list[float]] = defaultdict(list)

    for cat_key, cat_label in category_display:
        count = pair_counts.get(cat_key, 0)
        if count == 0:
            continue
        scores = category_scores.get(cat_key, {})
        cells: list[str] = []
        for m in metrics_order:
            val = scores.get(m, "—")
            if isinstance(val, float):
                cell = f"{val:.2f}"
                overall_scores[m].append(val)
            else:
                cell = str(val)
            cells.append(f"{cell:<{col_w}}")
        table_rows.append(f"| {cat_label:<12} | {count:^5} | " + " | ".join(cells) + " |")

    # Overall row (average over categories that produced numeric scores)
    overall_cells: list[str] = []
    for m in metrics_order:
        vals = overall_scores[m]
        if vals:
            overall_cells.append(f"{sum(vals) / len(vals):.2f}{'':<{col_w - 4}}")
        else:
            overall_cells.append(f"{'—':<{col_w}}")
    total_pairs = sum(pair_counts.values())
    table_rows.append(f"| **Overall**  | {total_pairs:^5} | " + " | ".join(overall_cells) + " |")

    # --- Hypotheses section ---
    hyp_lines: list[str] = []
    for hyp_key in ("H1", "H2", "H3", "H4"):
        evidence = hypotheses.get(hyp_key, "[PLACEHOLDER — A6 to stamp CONFIRMED or REFUTED]")
        hyp_lines.append(f"- **{hyp_key}**: {evidence}")

    # --- Failure inspection table ---
    fi_lines: list[str] = []
    if failure_inspection:
        fi_lines.append("| Pair id | Metric | Score | Failure mode | Bug filed |")
        fi_lines.append("|:--------|:-------|:------|:-------------|:----------|")
        for row in failure_inspection:
            fi_lines.append(
                f"| {row['pair_id']} | {row['metric']} | {row['score']} "
                f"| {row['failure_mode']} | {row.get('bug_filed', '—')} |"
            )
    else:
        fi_lines.append("*All pairs scored above the documented reference floor.*")

    # --- Known limitations ---
    kl_lines: list[str] = []
    if known_limitations:
        for note in known_limitations:
            kl_lines.append(f"- {note}")
    else:
        kl_lines.append("*None — all pairs evaluated without errors.*")

    content = f"""\
# Quality Baseline — {today}

> **Status**: Wave 2 scaffold — scores populated by A6 (Wave 3 RAGAS run).
> Hypothesis verdicts (CONFIRMED/REFUTED) to be stamped by A6 after evaluation.

## Per-category scores

{header_row}
{sep_row}
{chr(10).join(table_rows)}

## Hypotheses

{chr(10).join(hyp_lines)}

## Failure inspection

{chr(10).join(fi_lines)}

## Known limitations

{chr(10).join(kl_lines)}

## Reproduction

- **Dataset**: `{_SESSION_DIR}/golden-qa.yaml`
- **Command**: `zsh scripts/run-tests-external.sh -n spec28-ragas tests/quality/test_ragas_baseline.py`
- **Stack state at run time**: warm (one primer query recommended before the sweep)
- **Judge LLM**: {judge_label}
- **Backend git SHA**: {git_sha}
- **Session id**: {session_id}
- **Run duration**: {run_duration_s:.0f} seconds

## Ship-gate note

These scores are the v1.0.0 baseline. Per FR-018 and spec Assumptions, the
baseline is **informational, not a ship gate** — no score floor blocks v1.0.0.
Future PRs run the same harness; regressions against this baseline are flagged
for review.
"""
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    _QUALITY_METRICS_PATH.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ragas_baseline(
    golden_dataset: list[dict],
    backend_client: httpx.AsyncClient,
    ragas_metrics: list,
    session_id: str,
) -> None:
    """RAGAS quality baseline over the golden Q&A dataset.

    Runs the full evaluation pipeline:
      1. Query the backend for each pair.
      2. Evaluate with RAGAS.
      3. Write quality-metrics.md.

    Skips individual pairs on error and reports them in Known limitations.

    NOTE: This test requires the backend stack to be running (docker compose up).
    Run only via: zsh scripts/run-tests-external.sh -n spec28-ragas tests/quality/...
    """
    # Lazy imports — require pip install -e ".[quality]"
    from datasets import Dataset  # type: ignore[import]
    from ragas import evaluate as ragas_evaluate  # type: ignore[import]

    import subprocess
    import time

    start_time = time.monotonic()

    # --- Resolve git SHA for provenance ---
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        git_sha = "unknown"

    # --- Judge LLM label for quality-metrics.md Reproduction section ---
    judge_spec = os.environ.get("RAGAS_JUDGE", "local")
    model_name = os.environ.get("EMBEDINATOR_DEFAULT_LLM_MODEL", "qwen2.5:7b")
    if judge_spec == "local":
        judge_label = (
            f"Ollama `{model_name}` — same model as the backend; "
            "documents self-bias risk (neutral cloud judge: set RAGAS_JUDGE=openrouter:<model>)"
        )
    else:
        judge_label = f"{judge_spec} (external cloud judge)"

    # --- Accumulate data per category ---
    ragas_questions: list[str] = []
    ragas_answers: list[str] = []
    ragas_contexts: list[list[str]] = []
    ragas_ground_truths: list[str] = []
    ragas_pair_ids: list[str] = []
    ragas_categories: list[str] = []

    known_limitations: list[str] = []
    pair_counts: dict[str, int] = defaultdict(int)

    for pair in golden_dataset:
        pair_id: str = pair["id"]
        category: str = pair["category"]
        question: str = pair.get("question_es", "")
        reference: str = pair.get("reference_answer_es", "")
        expected: str = pair.get("expected_behavior", "answer")

        pair_counts[category] += 1

        if not question:
            known_limitations.append(f"{pair_id}: empty question_es — skipped.")
            continue

        # Each pair gets its own session to avoid cross-contamination.
        # For follow-up pairs, they share the session of their parent question.
        follow_up_of = pair.get("follow_up_of")
        pair_session_id = f"ragas-{session_id}-{pair_id}"
        if follow_up_of:
            # Re-use parent's session so the backend has conversational context.
            pair_session_id = f"ragas-{session_id}-{follow_up_of}"

        try:
            answer, contexts = await _stream_chat(
                client=backend_client,
                question=question,
                session_id=pair_session_id,
            )
        except Exception as exc:
            known_limitations.append(f"{pair_id} ({category}): backend query failed — {exc}. Skipped.")
            continue

        if expected in ("answer",) or category in _ANSWERABLE_CATEGORIES:
            # Standard RAGAS evaluation path.
            ragas_questions.append(question)
            ragas_answers.append(answer)
            ragas_contexts.append(contexts if contexts else ["(no context retrieved)"])
            ragas_ground_truths.append(reference)
            ragas_pair_ids.append(pair_id)
            ragas_categories.append(category)

        elif category in _DECLINE_CATEGORIES:
            # out-of-scope: check that the answer contains a decline phrase (H4).
            answer_lower = answer.lower()
            declined = any(phrase in answer_lower for phrase in _DECLINE_PHRASES)
            if not declined:
                known_limitations.append(
                    f"{pair_id} (out-of-scope): expected decline but answer did not "
                    f"contain a decline phrase. Answer: {answer[:120]!r}"
                )

        elif category in _DISAMBIGUATE_CATEGORIES:
            # ambiguous: note observed behavior for H4-adjacent analysis.
            known_limitations.append(f"{pair_id} (ambiguous): answer recorded for manual review — {answer[:120]!r}")

    # --- Run RAGAS evaluation ---
    category_scores: dict[str, dict[str, float | str]] = {}
    failure_inspection: list[dict[str, str]] = []

    if not ragas_questions:
        known_limitations.append("No answerable pairs could be evaluated (all errored or skipped).")
    else:
        dataset = Dataset.from_dict(
            {
                "question": ragas_questions,
                "answer": ragas_answers,
                "contexts": ragas_contexts,
                "ground_truth": ragas_ground_truths,
            }
        )

        try:
            result = ragas_evaluate(dataset=dataset, metrics=ragas_metrics)
        except Exception as exc:
            known_limitations.append(f"RAGAS evaluate() failed: {exc}. Scores not available.")
            result = None

        if result is not None:
            import pandas as pd  # ragas transitively installs pandas

            scores_df = pd.DataFrame(result.scores)
            scores_df["pair_id"] = ragas_pair_ids
            scores_df["category"] = ragas_categories

            # --- Aggregate per category ---
            metric_col_map = {
                "context_precision": "context_precision",
                "context_recall": "context_recall",
                "answer_relevancy": "answer_relevancy",
                "faithfulness": "faithfulness",
            }
            # Normalize column names: ragas may use snake_case or camelCase
            scores_df.columns = [c.lower().replace(" ", "_") for c in scores_df.columns]

            for cat, group in scores_df.groupby("category"):
                cat_scores: dict[str, float | str] = {}
                for ragas_col, our_key in metric_col_map.items():
                    if ragas_col in group.columns:
                        numeric = group[ragas_col].dropna()
                        if len(numeric) > 0:
                            cat_scores[our_key] = float(numeric.mean())
                        else:
                            cat_scores[our_key] = "N/A"
                    else:
                        cat_scores[our_key] = "—"
                category_scores[str(cat)] = cat_scores

            # --- Failure inspection ---
            for _, row in scores_df.iterrows():
                pair_id = row.get("pair_id", "?")
                for ragas_col, our_key in metric_col_map.items():
                    if ragas_col not in row:
                        continue
                    val = row[ragas_col]
                    if pd.isna(val):
                        continue
                    floor = _FLOOR_RETRIEVAL if "precision" in our_key or "recall" in our_key else _FLOOR_ANSWER
                    if float(val) < floor:
                        failure_inspection.append(
                            {
                                "pair_id": str(pair_id),
                                "metric": our_key,
                                "score": f"{float(val):.2f}",
                                "failure_mode": f"score below floor ({floor})",
                                "bug_filed": "—",
                            }
                        )

    # --- Hypothesis placeholders (A6 stamps verdicts after run) ---
    hypotheses = {
        "H1": (
            "[PLACEHOLDER] H1 — Spanish-on-English-embedder degradation: "
            "A6 to stamp CONFIRMED or REFUTED based on overall retrieval precision. "
            "Reference: community benchmarks suggest 15–30% degradation vs English corpora."
        ),
        "H2": (
            "[PLACEHOLDER] H2 — PDF table extraction edges: "
            "A6 to inspect pairs involving numeric tables (pipe diameters, flow rates). "
            "Confirm or refute based on whether malformed cells appear in retrieved contexts."
        ),
        "H3": (
            "[PLACEHOLDER] H3 — Citation cross-reference grounding: "
            "A6 to inspect Q-011/Q-013/Q-014 analytical pairs. "
            "Confirm if cross-document citations are missing; refute if both docs cited."
        ),
        "H4": (
            "[PLACEHOLDER] H4 — Out-of-scope graceful decline: "
            "A6 to review out-of-scope pair answers. "
            "Confirm if model hallucinated; refute if it correctly declined."
        ),
    }

    elapsed = time.monotonic() - start_time

    # --- Write quality-metrics.md ---
    _write_quality_metrics(
        session_id=session_id,
        category_scores=category_scores,
        hypotheses=hypotheses,
        failure_inspection=failure_inspection,
        known_limitations=known_limitations,
        judge_label=judge_label,
        git_sha=git_sha,
        run_duration_s=elapsed,
        pair_counts=dict(pair_counts),
    )

    # --- Final assertion ---
    # The test "passes" if quality-metrics.md was written successfully.
    # Numeric scores are informational (not a ship gate per FR-018).
    assert _QUALITY_METRICS_PATH.exists(), (
        f"quality-metrics.md was not written to {_QUALITY_METRICS_PATH}. "
        "Check the known_limitations section for errors."
    )
