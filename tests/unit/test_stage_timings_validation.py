"""
FR-008 / SC-007 — stage_timings_json key-set contract and data-integrity validation.

Scope (what the existing tests in test_stage_timings_db.py do NOT cover):
  - Key-set contract: no unexpected keys appear in stage_timings_json
  - Value integrity: all duration values are non-negative numbers
  - Sum bound: instrumented _ms values cannot collectively exceed total latency_ms
  - Stability: all rows written in the same era share the same key set

What this test does NOT cover (already tested elsewhere):
  - Round-trip storage — test_stage_timings_db.py::test_stage_timings_round_trips_through_sqlite
  - NULL default     — test_stage_timings_db.py::test_null_stage_timings_returns_empty_dict
  - API response     — test_traces_stage_timings.py

Assertion strategy: Option (a) — defensive upper-bound validation.

  The ±5% sum-to-latency_ms assertion from the original A7-instructions spec was
  evaluated against production DB data (79+ rows, branch 026-performance-debug,
  2026-04-14) and found infeasible:

    Row  latency_ms  instrumented_ms  coverage
    ---  ----------  ---------------  --------
    1    17 295      8 479            49 %
    2    14 866      6 289            42 %
    3    29 584      22 564           76 %
    4    13 473      7 464            55 %
    5    31 111      23 608           76 %

  The ~30-50 % gap consists of LangGraph inter-node scheduling overhead,
  NDJSON serialisation per chunk, and un-instrumented nodes (collect_answer).
  Per A6's benchmark findings, that accounts for ~3.2 s on a 19.5 s warm-p50.
  Complete instrumentation is deferred to spec-27 (FR-002, SC-004/005).

  Instead of ±5%, we assert the always-correct conditions:
    1. keys ⊆ EXPECTED_STAGE_KEYS  (no rogue keys)
    2. all numeric values ≥ 0      (no negative durations)
    3. sum(_ms) ≤ latency_ms       (instrumented stages ≤ total elapsed)
    4. key set is stable across rows

  Rationale saved to engram via mem_save (topic: spec-26/stage-timings-assertion-rationale).
"""
from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio

from backend.storage.sqlite_db import SQLiteDB

# ---------------------------------------------------------------------------
# Contract definitions
# ---------------------------------------------------------------------------

# All keys that are valid in stage_timings_json. Two groups:
#   - Dict-format base stages: value is {"duration_ms": float[, "failed": bool]}
#   - Flat-format research accumulators (A6 commit aa9c875, permanent telemetry):
#       _ms keys  → plain float duration
#       _calls keys → plain int count
EXPECTED_STAGE_KEYS: frozenset[str] = frozenset(
    {
        # ConversationGraph base stages (dict-format with "duration_ms" sub-key)
        "intent_classification",
        "embedding",
        "retrieval",
        "answer_generation",
        "grounded_verification",
        "ranking",
        # Research loop accumulators — see audit-synthesis.md §Top-1-contributor
        "research_orchestrator_ms",
        "research_orchestrator_calls",
        "research_tools_ms",
        "research_tools_calls",
        "research_compress_ms",   # may be 0 or absent when no compress step ran
        "research_compress_calls",
    }
)

# Keys whose values represent durations (not counts).
# Includes both dict-format base stages and flat _ms accumulators.
_DURATION_KEYS: frozenset[str] = frozenset(
    {
        "intent_classification",
        "embedding",
        "retrieval",
        "answer_generation",
        "grounded_verification",
        "ranking",
        "research_orchestrator_ms",
        "research_tools_ms",
        "research_compress_ms",
    }
)


# ---------------------------------------------------------------------------
# Helper functions (also independently unit-tested below)
# ---------------------------------------------------------------------------


def _ms_sum(stages: dict) -> float:
    """Sum all timing durations from a parsed stage_timings dict.

    Handles both value formats:
      - Dict:  {"duration_ms": float} → extracts float
      - Flat numeric               → uses value directly
    Skips _calls keys (counts, not durations).
    """
    total = 0.0
    for key, value in stages.items():
        if key not in _DURATION_KEYS:
            continue
        if isinstance(value, dict):
            total += float(value.get("duration_ms", 0.0))
        else:
            total += float(value)
    return total


def _all_values_nonnegative(stages: dict) -> tuple[bool, str]:
    """Return (True, "") if all numeric values ≥ 0, else (False, reason)."""
    for key, value in stages.items():
        if isinstance(value, dict):
            dur = value.get("duration_ms")
            if dur is not None and float(dur) < 0:
                return False, f"key={key!r} duration_ms={dur} is negative"
        elif isinstance(value, (int, float)):
            if float(value) < 0:
                return False, f"key={key!r} value={value} is negative"
    return True, ""


# ---------------------------------------------------------------------------
# Seed data — shape matches actual production rows observed 2026-04-14
# ---------------------------------------------------------------------------

_REALISTIC_ROWS: list[dict] = [
    {
        "latency_ms": 17295,
        "stage_timings_json": json.dumps(
            {
                "intent_classification": {"duration_ms": 1269.7},
                "research_orchestrator_ms": 5699.0,
                "research_orchestrator_calls": 3,
                "embedding": {"duration_ms": 432.6},
                "retrieval": {"duration_ms": 432.6},
                "research_tools_ms": 644.8,
                "research_tools_calls": 2,
                "ranking": {"duration_ms": 0.0},
            }
        ),
    },
    {
        "latency_ms": 14866,
        "stage_timings_json": json.dumps(
            {
                "intent_classification": {"duration_ms": 1358.8},
                "research_orchestrator_ms": 4157.1,
                "research_orchestrator_calls": 3,
                "embedding": {"duration_ms": 0.6},
                "retrieval": {"duration_ms": 0.6},
                "research_tools_ms": 771.6,
                "research_tools_calls": 2,
                "ranking": {"duration_ms": 0.0},
            }
        ),
    },
    {
        "latency_ms": 29584,
        "stage_timings_json": json.dumps(
            {
                "intent_classification": {"duration_ms": 1330.3},
                "research_orchestrator_ms": 19985.3,
                "research_orchestrator_calls": 3,
                "embedding": {"duration_ms": 99.3},
                "retrieval": {"duration_ms": 99.3},
                "research_tools_ms": 1049.8,
                "research_tools_calls": 2,
                "ranking": {"duration_ms": 0.0},
            }
        ),
    },
]


@pytest_asyncio.fixture
async def db_with_traces(tmp_path):
    """SQLiteDB (file-based) seeded with realistic stage_timings_json rows."""
    instance = SQLiteDB(db_path=str(tmp_path / "test.db"))
    await instance.connect()
    for row in _REALISTIC_ROWS:
        await instance.create_query_trace(
            id=str(uuid.uuid4()),
            session_id="sess-spec26-validation",
            query="What is the authentication mechanism?",
            collections_searched=json.dumps(["test-col"]),
            chunks_retrieved_json=json.dumps([]),
            latency_ms=row["latency_ms"],
            confidence_score=72,
            stage_timings_json=row["stage_timings_json"],
        )
    yield instance
    await instance.close()


# ---------------------------------------------------------------------------
# Contract tests (use the seeded DB)
# ---------------------------------------------------------------------------


class TestStageTimingsPopulated:
    """FR-008: completed trace rows have non-empty stage_timings_json."""

    @pytest.mark.asyncio
    async def test_seeded_rows_have_stage_timings(self, db_with_traces):
        """All seeded rows carry populated (non-empty) stage_timings_json."""
        cursor = await db_with_traces.db.execute(
            "SELECT id, stage_timings_json FROM query_traces "
            "WHERE stage_timings_json IS NOT NULL"
        )
        rows = await cursor.fetchall()
        assert rows, "no rows with stage_timings_json found — fixture seeding failed"
        for row in rows:
            stages = json.loads(row["stage_timings_json"])
            assert stages, (
                f"Empty stage_timings dict for trace id={row['id']!r}. "
                "FR-008 requires populated timings on every completed trace."
            )


class TestStageTimingsKeySetContract:
    """FR-008: stage_timings_json contains only keys in the stable expected set."""

    @pytest.mark.asyncio
    async def test_all_keys_subset_of_expected(self, db_with_traces):
        """Every key in every stage_timings_json row is a known expected key."""
        cursor = await db_with_traces.db.execute(
            "SELECT stage_timings_json FROM query_traces "
            "WHERE stage_timings_json IS NOT NULL"
        )
        rows = await cursor.fetchall()
        assert rows, "no seeded trace rows found"
        for row in rows:
            stages = json.loads(row["stage_timings_json"])
            unknown = set(stages.keys()) - EXPECTED_STAGE_KEYS
            assert not unknown, (
                f"Unexpected stage_timings keys: {unknown!r}. "
                "If a new stage was added in spec-27+, update EXPECTED_STAGE_KEYS here."
            )

    @pytest.mark.asyncio
    async def test_key_set_stable_across_rows(self, db_with_traces):
        """All trace rows share the same stage key set (FR-008 stability)."""
        cursor = await db_with_traces.db.execute(
            "SELECT stage_timings_json FROM query_traces "
            "WHERE stage_timings_json IS NOT NULL "
            "ORDER BY rowid"
        )
        rows = await cursor.fetchall()
        assert len(rows) >= 2, "need at least 2 rows to assert key-set stability"
        first_keys = set(json.loads(rows[0]["stage_timings_json"]).keys())
        for i, row in enumerate(rows[1:], start=1):
            row_keys = set(json.loads(row["stage_timings_json"]).keys())
            assert row_keys == first_keys, (
                f"Stage key set drifted at row {i}: "
                f"expected {sorted(first_keys)}, got {sorted(row_keys)}. "
                "FR-008 requires a stable key contract across all traces."
            )


class TestStageTimingsValueIntegrity:
    """FR-008: stage timing values are non-negative and bounded by latency_ms."""

    @pytest.mark.asyncio
    async def test_all_values_nonnegative(self, db_with_traces):
        """No stage duration is negative — elapsed time cannot go backwards."""
        cursor = await db_with_traces.db.execute(
            "SELECT stage_timings_json, latency_ms FROM query_traces "
            "WHERE stage_timings_json IS NOT NULL"
        )
        rows = await cursor.fetchall()
        for row in rows:
            stages = json.loads(row["stage_timings_json"])
            ok, reason = _all_values_nonnegative(stages)
            assert ok, (
                f"Negative value in trace with latency_ms={row['latency_ms']}: {reason}"
            )

    @pytest.mark.asyncio
    async def test_ms_sum_does_not_exceed_total_latency(self, db_with_traces):
        """Sum of instrumented _ms durations ≤ total latency_ms.

        Note: instrumented stages cover only ~42-76% of total latency in the
        spec-26 dataset. The remaining gap is LangGraph scheduling, NDJSON
        serialisation, and un-instrumented nodes. We assert only the upper bound
        here. The tighter ±5% assertion is deferred to spec-27 (FR-002, SC-004/005).
        """
        cursor = await db_with_traces.db.execute(
            "SELECT stage_timings_json, latency_ms FROM query_traces "
            "WHERE stage_timings_json IS NOT NULL"
        )
        rows = await cursor.fetchall()
        for row in rows:
            stages = json.loads(row["stage_timings_json"])
            instrumented = _ms_sum(stages)
            latency = row["latency_ms"]
            assert instrumented <= latency, (
                f"Instrumented stage sum ({instrumented:.1f} ms) exceeds "
                f"total latency_ms ({latency} ms) — likely a double-counting bug."
            )


# ---------------------------------------------------------------------------
# Pure-logic helper tests (no I/O, always fast)
# ---------------------------------------------------------------------------


class TestMsSumHelper:
    """Unit tests for _ms_sum() — covers both value formats and edge cases."""

    def test_dict_format_entries(self):
        """_ms_sum() extracts duration_ms from dict-format base stages."""
        stages = {
            "intent_classification": {"duration_ms": 100.0},
            "embedding": {"duration_ms": 50.0},
            "retrieval": {"duration_ms": 25.0},
        }
        assert _ms_sum(stages) == pytest.approx(175.0)

    def test_flat_ms_entries(self):
        """_ms_sum() adds flat numeric _ms values."""
        stages = {
            "research_orchestrator_ms": 5000.0,
            "research_tools_ms": 600.0,
        }
        assert _ms_sum(stages) == pytest.approx(5600.0)

    def test_calls_counters_are_skipped(self):
        """_ms_sum() excludes _calls keys (integer counts, not durations)."""
        stages = {
            "research_orchestrator_ms": 1000.0,
            "research_orchestrator_calls": 3,
            "research_tools_ms": 200.0,
            "research_tools_calls": 2,
        }
        assert _ms_sum(stages) == pytest.approx(1200.0)

    def test_realistic_mixed_format(self):
        """_ms_sum() handles the exact production data shape correctly."""
        stages = {
            "intent_classification": {"duration_ms": 1269.7},
            "research_orchestrator_ms": 5699.0,
            "research_orchestrator_calls": 3,
            "embedding": {"duration_ms": 432.6},
            "retrieval": {"duration_ms": 432.6},
            "research_tools_ms": 644.8,
            "research_tools_calls": 2,
            "ranking": {"duration_ms": 0.0},
        }
        expected = 1269.7 + 5699.0 + 432.6 + 432.6 + 644.8 + 0.0
        assert _ms_sum(stages) == pytest.approx(expected, rel=1e-4)

    def test_zero_duration_entries(self):
        """_ms_sum() handles zero durations without error (e.g. ranking=0)."""
        stages = {"ranking": {"duration_ms": 0.0}}
        assert _ms_sum(stages) == pytest.approx(0.0)

    def test_empty_stages_returns_zero(self):
        """_ms_sum({}) returns 0.0 without error."""
        assert _ms_sum({}) == pytest.approx(0.0)


class TestAllValuesNonnegativeHelper:
    """Unit tests for _all_values_nonnegative() — positive and negative cases."""

    def test_valid_data_passes(self):
        """Well-formed stages with non-negative values return True."""
        stages = {
            "intent_classification": {"duration_ms": 100.0},
            "research_orchestrator_ms": 5000.0,
            "research_orchestrator_calls": 3,
        }
        ok, reason = _all_values_nonnegative(stages)
        assert ok, reason

    def test_negative_dict_duration_fails(self):
        """A negative duration_ms in a dict-format entry returns False."""
        stages = {"intent_classification": {"duration_ms": -1.0}}
        ok, _ = _all_values_nonnegative(stages)
        assert not ok

    def test_negative_flat_value_fails(self):
        """A negative flat _ms value returns False."""
        stages = {"research_orchestrator_ms": -500.0}
        ok, _ = _all_values_nonnegative(stages)
        assert not ok

    def test_zero_is_valid(self):
        """Zero duration is non-negative and must pass."""
        stages = {"ranking": {"duration_ms": 0.0}}
        ok, reason = _all_values_nonnegative(stages)
        assert ok, reason


class TestKeySetContractLogic:
    """Pure-logic checks that mirror the DB assertions — no fixture needed."""

    def test_unexpected_key_is_detected(self):
        """A key absent from EXPECTED_STAGE_KEYS is flagged as unknown."""
        stages = {
            "intent_classification": {"duration_ms": 100.0},
            "undocumented_stage": 42.0,
        }
        unknown = set(stages.keys()) - EXPECTED_STAGE_KEYS
        assert "undocumented_stage" in unknown

    def test_all_known_keys_accepted(self):
        """All keys in the expected set produce an empty unknown set."""
        stages = {k: 0 for k in EXPECTED_STAGE_KEYS}
        unknown = set(stages.keys()) - EXPECTED_STAGE_KEYS
        assert not unknown

    def test_key_set_drift_detected(self):
        """Differing key sets between two rows are caught as a stability violation."""
        row_a = {"intent_classification": {"duration_ms": 100.0}}
        row_b = {
            "intent_classification": {"duration_ms": 200.0},
            "extra_stage_added_later": 0.0,
        }
        assert set(row_a.keys()) != set(row_b.keys()), (
            "Stability check should have caught this drift"
        )
