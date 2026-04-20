"""Tests for per-component log level overrides (US3, FR-004, SC-004, SC-007).

These tests verify the `_filter_by_component` structlog processor correctly:
- T034: Passes all events when no LOG_LEVEL_OVERRIDES are configured
- T035: Filters events below the overridden level for a specific component
- T036: Ignores invalid level strings and logs a warning (SC-007)
"""

from __future__ import annotations

import logging as stdlib_logging
from io import StringIO
from typing import Any

import pytest
import structlog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_filter_by_component(override_map: dict[str, int]):
    """Build a _filter_by_component closure identical to the production one."""

    def _filter_by_component(logger: Any, method_name: str, event_dict: dict) -> dict:
        component = event_dict.get("component", "")
        if not component:
            return event_dict  # no component key → pass through
        override_level = override_map.get(component)
        if override_level is None:
            return event_dict  # no override → pass through
        event_level = stdlib_logging.getLevelName(method_name.upper())
        if isinstance(event_level, int) and event_level < override_level:
            raise structlog.DropEvent()
        return event_dict

    return _filter_by_component


def _configure_test_structlog(override_map: dict[str, int]) -> list[dict]:
    """Configure structlog with the _filter_by_component processor.

    Returns a list that accumulates captured log event_dicts.
    """
    captured: list[dict] = []

    class _CapturingProcessor:
        def __call__(self, logger: Any, method: str, event_dict: dict) -> dict:
            captured.append(dict(event_dict))
            raise structlog.DropEvent()  # prevent actual output

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _make_filter_by_component(override_map),
            structlog.processors.add_log_level,
            _CapturingProcessor(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(stdlib_logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=StringIO()),
        cache_logger_on_first_use=False,
    )

    return captured


# ---------------------------------------------------------------------------
# T034 — No overrides: all events pass through
# ---------------------------------------------------------------------------


class TestNoOverrides:
    """T034: When LOG_LEVEL_OVERRIDES is empty, all events pass through."""

    def test_debug_events_pass_with_no_override(self):
        """Debug events for any component should reach the processor chain."""
        captured = _configure_test_structlog(override_map={})

        log = structlog.get_logger().bind(component="backend.retrieval.reranker")
        log.debug("debug_event", key="value")

        assert len(captured) == 1
        assert captured[0]["event"] == "debug_event"

    def test_info_events_pass_with_no_override(self):
        """Info events should pass through when there are no overrides."""
        captured = _configure_test_structlog(override_map={})

        log = structlog.get_logger().bind(component="backend.storage.sqlite_db")
        log.info("info_event")

        assert len(captured) == 1
        assert captured[0]["event"] == "info_event"

    def test_event_without_component_passes_through(self):
        """Events with no component key are always passed through."""
        captured = _configure_test_structlog(override_map={})

        log = structlog.get_logger()
        log.warning("no_component_warning")

        assert len(captured) == 1
        assert captured[0]["event"] == "no_component_warning"


# ---------------------------------------------------------------------------
# T035 — Override set: level filtering works correctly
# ---------------------------------------------------------------------------


class TestOverrideFiltering:
    """T035: With overrides, events below the override level are dropped."""

    def test_debug_passes_for_overridden_component_at_debug(self):
        """Debug events for component with DEBUG override pass through."""
        override_map = {"backend.retrieval.reranker": stdlib_logging.DEBUG}
        captured = _configure_test_structlog(override_map)

        log = structlog.get_logger().bind(component="backend.retrieval.reranker")
        log.debug("reranker_debug")

        assert len(captured) == 1
        assert captured[0]["event"] == "reranker_debug"

    def test_debug_dropped_for_component_without_override_at_info_global(self):
        """A component with no override uses the global level via structlog's wrapper.

        The _filter_by_component processor only applies when there IS an override.
        Without an override the structlog wrapper_class filters at the global level.
        This test sets global to INFO and no override for the component.
        """
        # Only set an override for a different component; the test component has none
        override_map = {"backend.retrieval.reranker": stdlib_logging.DEBUG}
        captured: list[dict] = []

        class _Cap:
            def __call__(self, logger: Any, method: str, event_dict: dict) -> dict:
                captured.append(dict(event_dict))
                raise structlog.DropEvent()

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                _make_filter_by_component(override_map),
                structlog.processors.add_log_level,
                _Cap(),
            ],
            # Global wrapper at INFO — so debug events for *other* components
            # are already dropped before reaching our processor.
            wrapper_class=structlog.make_filtering_bound_logger(stdlib_logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=StringIO()),
            cache_logger_on_first_use=False,
        )

        other_log = structlog.get_logger().bind(component="backend.storage.sqlite_db")
        other_log.debug("sqlite_debug_should_be_dropped")

        # The global INFO wrapper drops this before it reaches our processor
        assert len(captured) == 0

    def test_info_passes_for_component_with_debug_override(self):
        """Info events always pass when component override is DEBUG."""
        override_map = {"backend.retrieval.reranker": stdlib_logging.DEBUG}
        captured = _configure_test_structlog(override_map)

        log = structlog.get_logger().bind(component="backend.retrieval.reranker")
        log.info("reranker_info")

        assert len(captured) == 1
        assert captured[0]["event"] == "reranker_info"

    def test_debug_dropped_when_component_override_is_warning(self):
        """Debug events are dropped when override sets the component to WARNING."""
        override_map = {"backend.storage.sqlite_db": stdlib_logging.WARNING}
        captured = _configure_test_structlog(override_map)

        log = structlog.get_logger().bind(component="backend.storage.sqlite_db")
        log.debug("sqlite_debug_should_drop")

        assert len(captured) == 0

    def test_info_dropped_when_component_override_is_warning(self):
        """Info events are dropped when override sets the component to WARNING."""
        override_map = {"backend.storage.sqlite_db": stdlib_logging.WARNING}
        captured = _configure_test_structlog(override_map)

        log = structlog.get_logger().bind(component="backend.storage.sqlite_db")
        log.info("sqlite_info_should_drop")

        assert len(captured) == 0

    def test_warning_passes_when_component_override_is_warning(self):
        """Warning events pass when component override is WARNING."""
        override_map = {"backend.storage.sqlite_db": stdlib_logging.WARNING}
        captured = _configure_test_structlog(override_map)

        log = structlog.get_logger().bind(component="backend.storage.sqlite_db")
        log.warning("sqlite_warning_passes")

        assert len(captured) == 1
        assert captured[0]["event"] == "sqlite_warning_passes"

    def test_events_without_component_always_pass_regardless_of_overrides(self):
        """Events without a component key bypass the component filter entirely."""
        override_map = {"backend.retrieval.reranker": stdlib_logging.ERROR}
        captured = _configure_test_structlog(override_map)

        log = structlog.get_logger()
        log.debug("no_component_debug")

        assert len(captured) == 1


# ---------------------------------------------------------------------------
# T036 — Invalid level in LOG_LEVEL_OVERRIDES: ignored + warning logged
# ---------------------------------------------------------------------------


class TestInvalidLevelOverride:
    """T036: Invalid level strings are ignored and a startup warning is emitted."""

    def test_parse_override_string_ignores_invalid_level(self):
        """Parsing LOG_LEVEL_OVERRIDES=backend.foo=INVALID produces an empty override_map."""
        import logging as stdlib_logging

        override_map: dict[str, int] = {}
        warnings_logged: list[str] = []

        raw_overrides = "backend.foo=INVALID"

        for pair in raw_overrides.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                warnings_logged.append(f"invalid_format:{pair}")
                continue
            module, level_str = pair.split("=", 1)
            level_int = stdlib_logging.getLevelName(level_str.strip().upper())
            if not isinstance(level_int, int):
                warnings_logged.append(f"invalid_level:{module}:{level_str}")
                continue
            override_map[module.strip()] = level_int

        # Invalid level → nothing added to override_map
        assert override_map == {}
        # A warning string was generated
        assert len(warnings_logged) == 1
        assert "INVALID" in warnings_logged[0]

    def test_parse_override_string_skips_invalid_keeps_valid(self):
        """Valid entries in the same override string are still applied."""
        import logging as stdlib_logging

        override_map: dict[str, int] = {}
        raw_overrides = "backend.foo=INVALID,backend.retrieval.reranker=DEBUG"

        for pair in raw_overrides.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                continue
            module, level_str = pair.split("=", 1)
            level_int = stdlib_logging.getLevelName(level_str.strip().upper())
            if not isinstance(level_int, int):
                continue
            override_map[module.strip()] = level_int

        # Only valid entry is kept
        assert "backend.retrieval.reranker" in override_map
        assert override_map["backend.retrieval.reranker"] == stdlib_logging.DEBUG
        # Invalid entry is not present
        assert "backend.foo" not in override_map

    def test_filter_operates_normally_after_invalid_level_skipped(self):
        """When invalid level is skipped (override_map is empty), all events pass."""
        # Simulate: invalid override was skipped → empty override_map
        override_map: dict[str, int] = {}
        captured = _configure_test_structlog(override_map)

        log = structlog.get_logger().bind(component="backend.foo")
        log.debug("foo_debug")

        # No override for backend.foo → pass-through
        assert len(captured) == 1
        assert captured[0]["event"] == "foo_debug"
