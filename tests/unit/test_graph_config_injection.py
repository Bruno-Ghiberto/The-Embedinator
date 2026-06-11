"""Regression test for BUG-045: LangGraph config injection broken by PEP 563.

Commit 3a5fe6b changed node signatures to `config: RunnableConfig | None = None`.
Under `from __future__ import annotations` (PEP 563), that annotation is
stringified to "RunnableConfig | None". LangGraph's KWARGS_CONFIG_KEYS only
accepts RunnableConfig, "RunnableConfig", Optional[RunnableConfig], or
"Optional[RunnableConfig]" — it does NOT accept "RunnableConfig | None".

When the annotation is unrecognised, add_node() emits a UserWarning and SKIPS
config injection, so every node receives config=None → llm=None → AttributeError
→ 100% chat failure (NDJSON SERVICE_UNAVAILABLE).

Fix: use `Optional[RunnableConfig]` which stringifies to "Optional[RunnableConfig]",
which IS in LangGraph's accept list.

This test builds all three graphs (ConversationGraph, ResearchGraph,
MetaReasoningGraph) and asserts zero UserWarnings that mention 'config'
parameter typing. It would have caught the regression in 3a5fe6b immediately.
"""

from __future__ import annotations

import warnings

import pytest


class TestNoConfigInjectionWarnings:
    """Ensure all graph compilations produce zero LangGraph config-typing warnings."""

    def test_conversation_graph_no_config_warnings(self):
        """build_conversation_graph() must emit zero config-typing UserWarnings."""
        from tests.mocks import build_mock_research_graph
        from backend.agent.conversation_graph import build_conversation_graph

        mock_research = build_mock_research_graph()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            build_conversation_graph(research_graph=mock_research)

        config_warnings = [
            w
            for w in caught
            if issubclass(w.category, UserWarning)
            and "config" in str(w.message).lower()
            and "parameter" in str(w.message).lower()
        ]
        assert config_warnings == [], (
            f"Found {len(config_warnings)} LangGraph config-injection warning(s) "
            f"in ConversationGraph — nodes will receive config=None at runtime:\n"
            + "\n".join(f"  {w.filename}:{w.lineno}: {w.message}" for w in config_warnings)
        )

    def test_research_graph_no_config_warnings(self):
        """build_research_graph() must emit zero config-typing UserWarnings."""
        from backend.agent.research_graph import build_research_graph

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            build_research_graph(tools=[])

        config_warnings = [
            w
            for w in caught
            if issubclass(w.category, UserWarning)
            and "config" in str(w.message).lower()
            and "parameter" in str(w.message).lower()
        ]
        assert config_warnings == [], (
            f"Found {len(config_warnings)} LangGraph config-injection warning(s) "
            f"in ResearchGraph — nodes will receive config=None at runtime:\n"
            + "\n".join(f"  {w.filename}:{w.lineno}: {w.message}" for w in config_warnings)
        )

    def test_research_graph_with_meta_reasoning_no_config_warnings(self):
        """build_research_graph(meta_reasoning_graph=...) must not warn on the inline mapper."""
        from backend.agent.research_graph import build_research_graph
        from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph

        meta_graph = build_meta_reasoning_graph()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            build_research_graph(tools=[], meta_reasoning_graph=meta_graph)

        config_warnings = [
            w
            for w in caught
            if issubclass(w.category, UserWarning)
            and "config" in str(w.message).lower()
            and "parameter" in str(w.message).lower()
        ]
        assert config_warnings == [], (
            f"Found {len(config_warnings)} LangGraph config-injection warning(s) "
            f"in ResearchGraph+meta_reasoning_mapper — nodes will receive config=None at runtime:\n"
            + "\n".join(f"  {w.filename}:{w.lineno}: {w.message}" for w in config_warnings)
        )

    def test_meta_reasoning_graph_no_config_warnings(self):
        """build_meta_reasoning_graph() must emit zero config-typing UserWarnings."""
        from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            build_meta_reasoning_graph()

        config_warnings = [
            w
            for w in caught
            if issubclass(w.category, UserWarning)
            and "config" in str(w.message).lower()
            and "parameter" in str(w.message).lower()
        ]
        assert config_warnings == [], (
            f"Found {len(config_warnings)} LangGraph config-injection warning(s) "
            f"in MetaReasoningGraph — nodes will receive config=None at runtime:\n"
            + "\n".join(f"  {w.filename}:{w.lineno}: {w.message}" for w in config_warnings)
        )
