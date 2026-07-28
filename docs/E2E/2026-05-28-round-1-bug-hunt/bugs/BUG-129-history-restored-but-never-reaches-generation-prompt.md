# BUG-129: History is restored into state but never reaches the answer-generation prompt

- **Severity**: MAJOR
- **Layer**: Reasoning
- **Discovered**: 2026-07-28T14:52:00Z in Phase 7 (P7-S5)
- **Phase scenario**: P7-S5
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. Hold a multi-turn conversation so history accumulates in the thread's checkpoint.
2. Ask a question that can only be answered from history — e.g. "What was my previous question in this conversation?"
3. Observe the assistant echoes the current question back instead of answering from history.
4. Repeat on a NORMALLY-COMPLETED control thread (no interruption, no restart): the same failure occurs, which rules out interruption and resume as the cause.
5. Confirm the history is genuinely present in state: the checkpoint blob is 106KB and contains `HumanMessage` x2, `AIMessage` x5, and prior-question terms x8-12.
6. Read `collect_answer` (`backend/agent/research_nodes.py:604-742`) — it contains **zero** references to `messages` across all 139 lines; its docstring reads *"Reads: sub_question, retrieved_chunks"*.

## Expected
The node that generates the answer has access to the conversation history the system persists, restores across restarts, and already injects into two other nodes — so a follow-up like "tell me more about that" can work.

## Actual
There is no path from restored history to the generator. Conversation history is persisted, restored, and injected into `classify_intent` and `rewrite_query` — but never into `collect_answer`, the only node that produces answer text. Multi-turn questions therefore cannot be answered, on any thread, interrupted or not.

## Artifacts
- Screenshot: null
- Log excerpt: null
- Trace: traces/P7-S1-ckpt-inflight.txt (gitignored) — checkpoint durability evidence for the same thread family

## Root-cause hypothesis
HIGH confidence, source-confirmed — four independently verified links, and the conclusion is structural rather than behavioural:
1. `collect_answer` (`research_nodes.py:604-742`) is the ONLY node that generates answer text, and references `messages` **zero** times in 139 lines.
2. Its LLM call (`:685-689`) passes exactly two messages: `SystemMessage(COLLECT_ANSWER_SYSTEM.format(passages=...))` and `HumanMessage(f"Sub-question: {state['sub_question']}")`. Nothing else.
3. `COLLECT_ANSWER_SYSTEM` has exactly ONE format slot, `{passages}` — enumerated programmatically. There is no history slot to fill even if a caller wanted to.
4. The system prompt instructs the model to answer *"using ONLY the retrieved passages below"* — so even if history were present, it is explicitly forbidden.

This is **not** "history is passed but ignored". There is no path. Fix surface: add a history slot to `COLLECT_ANSWER_SYSTEM` and pass the restored `messages` into `collect_answer`, and relax the use-ONLY-passages instruction enough to permit conversational reference without weakening grounding.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/177
- **Rationale**: The product presents a multi-turn chat interface in which no follow-up that depends on prior turns can ever be answered, because the generating node has no access to the history the system already persists and restores.

## Notes
Reporter: log-analyst (source verification), team-lead (adjudication). Title compressed from the routed wording — "Conversation history is restored into state but never reaches the answer-generation prompt" measured **89 chars**, over the schema's 80-char `maxLength`; shortened to 76 chars with the checkable claim intact (precedent: BUG-113 at P6-S3).

**THE ASYMMETRY IS THE FINDING**, and it is sharper than "multi-turn memory is broken":

| Node | History injected |
|---|---|
| `classify_intent` (`nodes.py:186-196`, `:207-212`) | **last 10 messages** |
| `rewrite_query` (`nodes.py:271`) | **last 6 messages** |
| `collect_answer` — the generator | **none** |

History reaches the two nodes where it causes HARM — overloading a 7B classifier until it hard-fails — and never reaches the one node where it would provide VALUE. **Cross-reference BUG-069 explicitly: these are two faces of the same misrouting, not independent defects.** BUG-069 is the damage the injected history does; this record is the value it fails to deliver.

**Harm without benefit from the same state**: prior-turn `sub_answers` DO accumulate in `ConversationState` (`num_valid` escalating 1→2→3 across turns), and that accumulation drives the citation growth re-observed today (11→168 within one turn, BUG-070). So prior answers accumulate enough to bloat the payload while never serving as generation context.

**Why the echo happened — recorded so it is not later misread as a model failure.** `collect_answer` received literally `Sub-question: What was my previous question in this conversation?` plus off-topic gas-regulation passages, under a use-ONLY-passages instruction. Restating the question is the PREDICTABLE output of that prompt. qwen2.5:7b followed its instructions exactly; this is not a model-quality defect.

**Severity MAJOR, with the counter-argument and its rebuttal recorded.** One could argue a strict RAG system SHOULD answer only from documents. Rebuttal: the system already invests in persisting history, restoring it across full-stack restarts, and injecting it into two other nodes — so this is an OMISSION AT THE POINT OF USE, not a design stance. In a product presenting a multi-turn chat UI, "tell me more about that" cannot work.

**Method — the control arm is what made this diagnosable.** The same failure on a normally-completed thread ruled out the model-artifact explanation BEFORE the source read even began. Had only the interrupted thread been tested, this would have been misfiled as a resume defect and attributed to Phase 7's fault injection.

**P7-S5 card verdict FAIL — and explicitly NOT for the reason the stale playbook predicted.** Checkpoint persistence IS wired and works (`main.py:575-577`, `:640-644`); 13 checkpoints survived a full-stack restart and resume restores state correctly. The STATE is not the problem. The playbook's "MemorySaver default → automatic CRITICAL" branch was correctly neutralized at phase open and this record confirms that neutralization was right: the defect is downstream of persistence entirely.
