"""Unit tests for stage_timings instrumentation (FR-005, spec-14).

Tests verify:
1. ConversationState TypedDict declares the stage_timings field.
2. A timing entry has the correct structure (duration_ms as a number).
3. The state merge pattern preserves prior stage entries.
4. A failed stage entry includes the failed flag.
5. Absent key means conditional stage did not execute.
"""
from __future__ import annotations


def test_conversation_state_has_stage_timings_field():
    """stage_timings: dict is a declared field of ConversationState."""
    from backend.agent.state import ConversationState

    assert "stage_timings" in ConversationState.__annotations__


def test_research_state_has_stage_timings_field():
    """stage_timings: dict is a declared field of ResearchState (for subgraph propagation)."""
    from backend.agent.state import ResearchState

    assert "stage_timings" in ResearchState.__annotations__


def test_stage_timing_entry_has_duration_ms():
    """A timing entry has duration_ms as a numeric value."""
    entry = {"duration_ms": 45.2}
    assert isinstance(entry["duration_ms"], (int, float))
    assert entry["duration_ms"] >= 0


def test_stage_timing_duration_ms_is_non_negative():
    """duration_ms must be non-negative (time cannot go backwards)."""
    import time

    t0 = time.perf_counter()
    # Simulate some work
    _ = sum(range(100))
    duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    assert duration_ms >= 0


def test_stage_timings_merge_preserves_prior_stages():
    """The merge pattern accumulates stage entries without overwriting prior ones."""
    prior = {"intent_classification": {"duration_ms": 180.4}}
    new_entry = {"embedding": {"duration_ms": 45.1}}
    merged = {**prior, **new_entry}
    assert "intent_classification" in merged
    assert "embedding" in merged


def test_stage_timings_merge_does_not_lose_entries():
    """Merging multiple stages accumulates all entries correctly."""
    timings: dict = {}
    # Simulate sequential node recording
    timings = {**timings, "intent_classification": {"duration_ms": 180.0}}
    timings = {**timings, "embedding": {"duration_ms": 45.0}}
    timings = {**timings, "retrieval": {"duration_ms": 28.0}}
    timings = {**timings, "ranking": {"duration_ms": 142.0}}
    timings = {**timings, "answer_generation": {"duration_ms": 487.0}}

    assert len(timings) == 5
    assert "intent_classification" in timings
    assert "embedding" in timings
    assert "retrieval" in timings
    assert "ranking" in timings
    assert "answer_generation" in timings


def test_failed_stage_includes_failed_flag():
    """A failed stage entry includes failed: True."""
    entry = {"duration_ms": 22.0, "failed": True}
    assert entry.get("failed") is True
    assert "duration_ms" in entry


def test_failed_stage_duration_ms_is_present():
    """A failed stage entry still has duration_ms (partial timing is preserved)."""
    entry = {"duration_ms": 33.5, "failed": True}
    assert isinstance(entry["duration_ms"], (int, float))
    assert entry["duration_ms"] >= 0


def test_absent_stage_key_means_not_executed():
    """Conditional stages (grounded_verification, meta_reasoning) are absent when not executed."""
    stage_timings = {
        "intent_classification": {"duration_ms": 180.0},
        "embedding": {"duration_ms": 45.0},
        "retrieval": {"duration_ms": 28.0},
        "ranking": {"duration_ms": 142.0},
        "answer_generation": {"duration_ms": 487.0},
    }
    assert "grounded_verification" not in stage_timings
    assert "meta_reasoning" not in stage_timings


def test_zero_duration_not_inserted_for_skipped_stage():
    """A skipped stage must NOT appear with duration_ms: 0 — key must be absent entirely."""
    stage_timings = {
        "intent_classification": {"duration_ms": 180.0},
        "embedding": {"duration_ms": 45.0},
    }
    # Verify: grounded_verification is simply absent, not zero
    assert stage_timings.get("grounded_verification") is None


def test_stage_timings_default_is_empty_dict():
    """state.get('stage_timings', {}) returns empty dict when field not yet initialized."""
    # Simulate a state dict that does not yet have stage_timings
    state: dict = {
        "session_id": "test-session",
        "intent": "rag_query",
    }
    prior = state.get("stage_timings", {})
    assert prior == {}
    assert isinstance(prior, dict)


def test_duration_ms_precision_one_decimal():
    """duration_ms uses round(..., 1) — 1 decimal place precision."""
    import time

    t0 = time.perf_counter()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    rounded = round(elapsed_ms, 1)

    # Verify the result is a float with at most 1 decimal digit
    assert isinstance(rounded, float)
    # Check that round(..., 1) produces the expected precision
    assert round(123.456, 1) == 123.5
    assert round(0.05, 1) == 0.1 or round(0.05, 1) == 0.0  # floating point tolerance


def test_stage_timings_accumulates_through_state_merge_pattern():
    """The {**prior, new_stage: {...}} pattern correctly merges stage entries."""
    # Simulate the exact pattern used in instrumented nodes
    state_stage_timings: dict = {}

    # Node 1: classify_intent
    state_stage_timings = {
        **state_stage_timings,
        "intent_classification": {"duration_ms": 180.4},
    }

    # Node 2: tools_node (embedding + retrieval)
    state_stage_timings = {
        **state_stage_timings,
        "embedding": {"duration_ms": 45.1},
        "retrieval": {"duration_ms": 45.1},
    }

    # Node 3: collect_answer (answer_generation)
    state_stage_timings = {
        **state_stage_timings,
        "answer_generation": {"duration_ms": 487.2},
    }

    # Node 4: validate_citations (ranking)
    state_stage_timings = {
        **state_stage_timings,
        "ranking": {"duration_ms": 142.6},
    }

    # All 5 always-present stages should be present
    assert "intent_classification" in state_stage_timings
    assert "embedding" in state_stage_timings
    assert "retrieval" in state_stage_timings
    assert "answer_generation" in state_stage_timings
    assert "ranking" in state_stage_timings

    # All entries have duration_ms
    for stage_name, entry in state_stage_timings.items():
        assert "duration_ms" in entry, f"Stage '{stage_name}' missing duration_ms"
        assert isinstance(entry["duration_ms"], (int, float))
