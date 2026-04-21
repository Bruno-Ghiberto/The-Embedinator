"""Regression guard for spec-26 tuned configuration defaults.

FR-009 requires every knob changed by spec-26 to be traceable:
- source comment on the default in backend/config.py
- row in specs/026-performance-debug/audit.md §ConfigChanges
- this test locking in the tuned value so a future PR cannot silently revert it

SC-009 checks that every changed default carries a `# spec-26: <reason>` comment
(see grep-based check in the verification block of A6-instructions.md); this test
is the behavioral counterpart — Settings() with no env overrides must produce
the tuned values exactly.
"""

from backend.config import Settings


def test_spec26_groundedness_disabled_by_default():
    """FR-005 top-1 fix — verify_groundedness skipped unless opted in."""
    s = Settings()
    assert s.groundedness_check_enabled is False


def test_spec26_default_llm_is_qwen():
    """FR-004 — default model reverted to non-thinking qwen2.5:7b (A3's Wave 2)."""
    s = Settings()
    assert s.default_llm_model == "qwen2.5:7b"


def test_spec26_supported_llm_models_includes_defaults():
    """FR-004 — supported_llm_models published list must include the default."""
    s = Settings()
    assert "qwen2.5:7b" in s.supported_llm_models
    assert "llama3.1:8b" in s.supported_llm_models
    assert "mistral:7b" in s.supported_llm_models


def test_spec26_embed_max_workers_tuned():
    """BUG-023 opportunistic P3 — 20-thread reference CPU, 12 workers aligns headroom."""
    s = Settings()
    assert s.embed_max_workers >= 12


def test_spec26_circuit_breaker_cooldown_tuned():
    """FR-009 — 30s lockout too aggressive for single-user workstation."""
    s = Settings()
    assert s.circuit_breaker_cooldown_secs >= 60


def test_spec26_checkpoint_max_threads_bounded():
    """DISK-001 — LangGraph checkpoints.db growth is capped (A3's Wave 2)."""
    s = Settings()
    assert s.checkpoint_max_threads > 0
    assert s.checkpoint_max_threads <= 1000


def test_spec26_max_iterations_capped():
    """FR-005 iter2 — research-loop cap; smoke bench showed 4-call median, 3 prevents explosion."""
    s = Settings()
    assert s.max_iterations <= 3
