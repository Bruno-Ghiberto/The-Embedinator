"""Mock ResearchGraph for testing the ConversationGraph.

Provides build_mock_research_graph() which returns a compiled StateGraph(ResearchState)
that immediately returns a fixed SubAnswer without any LLM or retrieval calls.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from backend.agent.schemas import Citation, SubAnswer
from backend.agent.state import ResearchState


def _mock_research_node(state: ResearchState) -> dict:
    """Return a fixed SubAnswer for testing purposes."""
    sub_question = state["sub_question"]

    citation = Citation(
        passage_id="mock-passage-001",
        document_id="mock-doc-001",
        document_name="Mock Document",
        start_offset=0,
        end_offset=100,
        text="This is a mock passage used for testing.",
        relevance_score=0.85,
    )

    sub_answer = SubAnswer(
        sub_question=sub_question,
        answer=f"Mock answer for: {sub_question}",
        citations=[citation],
        chunks=[],
        confidence_score=85,
    )

    return {
        "answer": sub_answer.answer,
        "citations": [citation],
        "confidence_score": 0.85,
    }


def build_simple_chat_graph():
    """Build a minimal ConversationGraph for Phase 1 integration tests.

    No LLM or DB dependencies. Returns a fixed response with AIMessage
    so that streaming and metadata frames work correctly.
    """
    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.memory import MemorySaver

    from backend.agent.state import ConversationState

    def respond(state):
        response = "The capital of France is Paris."
        return {
            "messages": state["messages"] + [AIMessage(content=response)],
            "final_response": response,
            "citations": [],
            "confidence_score": 85,
            "intent": "rag_query",
        }

    graph = StateGraph(ConversationState)
    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=MemorySaver())


def build_mock_research_graph() -> StateGraph:
    """Build a compiled mock ResearchGraph that returns fixed SubAnswer data.

    Returns:
        A compiled StateGraph(ResearchState) suitable for injection into
        build_conversation_graph(research_graph=...).
    """
    graph = StateGraph(ResearchState)
    graph.add_node("research_node", _mock_research_node)
    graph.add_edge(START, "research_node")
    graph.add_edge("research_node", END)
    return graph.compile()
