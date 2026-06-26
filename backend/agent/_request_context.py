"""Per-request context propagated from the API layer to agent tools.

This module is the single source of truth for request-scoped context that must
be accessible deep inside LangGraph tool closures without being threaded through
every function signature.

Usage:
    # In the API handler (chat.py) — set once per request, before graph invocation:
    from backend.agent._request_context import selected_collections_var
    selected_collections_var.set(list(body.collection_ids))

    # In the tool closure (tools.py) — read at call time:
    from backend.agent._request_context import selected_collections_var
    authorized = selected_collections_var.get()

Design note:
    Python contextvars are propagated to asyncio tasks spawned from the current
    task at creation time (PEP 567 / asyncio copy-context semantics). LangGraph
    uses asyncio internally, so context set in the request handler is inherited
    by all sub-tasks including tool invocations inside the research subgraph.

spec-28 BUG-002: closes the silent fallback to search_all_collections when the
LLM passes a raw UUID instead of the emb-{uuid} Qdrant form.
"""

import contextvars

# Per-request authorized collection allowlist.
# Value: list of raw UUIDs from body.collection_ids (no "emb-" prefix).
# Default: empty list — tools must check and fail-closed if not set.
selected_collections_var: contextvars.ContextVar[list[str]] = contextvars.ContextVar(
    "selected_collections_var", default=[]
)
