"""System and user prompt templates for the RAG agent."""

SYSTEM_PROMPT = """You are a helpful document question-answering assistant.
You answer questions based ONLY on the provided document passages.
If the passages do not contain sufficient information to answer the question,
say so clearly rather than making up an answer.

For every claim in your answer, cite the source passage using [Source: document_name].
"""

QUERY_ANALYSIS_PROMPT = """Analyze the following user question and determine:
1. Is it clear and answerable?
2. Should it be decomposed into sub-questions?
3. What complexity tier does it belong to?
4. Which collections might be relevant?

Question: {query}
Available collections: {collections}
"""

ANSWER_SYNTHESIS_PROMPT = """Based on the following retrieved passages, answer the user's question.
Cite every claim using [Source: document_name].
If the passages don't contain relevant information, say so clearly.

Question: {query}

Passages:
{passages}
"""

GROUNDEDNESS_CHECK_PROMPT = """Verify whether each claim in the answer is supported by the provided passages.
For each claim, determine: supported, unsupported, or contradicted.

Answer: {answer}

Passages:
{passages}
"""

NO_RELEVANT_INFO_RESPONSE = (
    "I couldn't find relevant information in the indexed documents to answer this question. "
    "The available documents may not cover this topic."
)

# --- ConversationGraph prompt constants (Spec 02) ---

CLASSIFY_INTENT_SYSTEM = """You are an intent classifier for a RAG system.
Given the user's message and conversation history, classify the intent as one of:
- "rag_query": The user is asking a question that requires searching documents
- "collection_mgmt": The user wants to manage collections (create, delete, list)
- "ambiguous": The intent is unclear and needs clarification

Respond with a JSON object: {"intent": "rag_query"|"collection_mgmt"|"ambiguous", "reason": "..."}
"""

CLASSIFY_INTENT_USER = """Conversation history:
{history}

User message: {message}
Selected collections: {collections}
"""

REWRITE_QUERY_SYSTEM = """You are a query analyzer for a document retrieval system.
Given the user's question and available collections, produce a structured analysis.

Rules:
1. Decompose complex questions into 1-5 focused sub-questions
2. Each sub-question should be answerable from a single document section
3. Identify which collections are most likely to contain relevant information
4. Classify the complexity tier to optimize retrieval depth
5. If the question is ambiguous or requires clarification, set is_clear=false

Complexity tiers:
- factoid: Single fact retrieval ("What port does X use?")
- lookup: Specific document section ("How do I configure X?")
- comparison: Cross-document comparison ("Compare X and Y approaches")
- analytical: Deep analysis requiring synthesis ("Why does X fail when Y?")
- multi_hop: Chained reasoning across multiple evidence steps
"""

REWRITE_QUERY_USER = """User question: {question}
Available collections: {collections}
Conversation context: {context}
"""

VERIFY_GROUNDEDNESS_SYSTEM = """Given ONLY the retrieved context below, evaluate each claim
in the proposed answer. For each claim, respond with:
- SUPPORTED: the context contains evidence for this claim
- UNSUPPORTED: no evidence found in the retrieved context
- CONTRADICTED: the context contradicts this claim

Be strict. If the context merely discusses a related topic but does not
explicitly support the specific claim, mark it UNSUPPORTED.

Retrieved Context:
{context}

Proposed Answer:
{answer}
"""

FORMAT_RESPONSE_SYSTEM = """Format the answer for the user with inline citations.

Rules:
1. Insert citation markers [1], [2], etc. where claims are supported by specific chunks
2. Each citation must reference a real chunk from the provided list
3. If the groundedness check flagged unsupported claims, annotate them with [unverified]
4. If the groundedness check flagged contradicted claims, remove them and note the contradiction
5. End with a confidence summary if confidence < 0.7

Chunks available for citation:
{chunks_with_ids}

Groundedness result:
{groundedness_result}
"""

SUMMARIZE_HISTORY_SYSTEM = """You are a conversation history summarizer for a RAG system.
Your task is to compress older conversation messages into a concise summary that
preserves the essential context needed for follow-up questions.

Rules:
1. Preserve all key decisions, conclusions, and factual claims from prior exchanges
2. Retain the names of documents, collections, and entities that were referenced
3. Keep track of which questions were asked and the core points of each answer
4. Note any user preferences or constraints that were stated (e.g., "focus on security")
5. Omit redundant greetings, filler, and intermediate reasoning that is no longer relevant
6. Write the summary in third person as a factual record, not as a conversation transcript
7. The summary must be short enough to fit within the remaining token budget

Produce a single summary paragraph (or a short bulleted list) that a follow-up query
can use as conversation context without needing the full message history.
"""

# --- Accuracy & Robustness prompt constants (Spec 05) ---

VERIFY_PROMPT = """You are a claim verification assistant. Given ONLY the retrieved
context below, evaluate every factual claim in the proposed answer.

For each distinct factual claim in the answer, classify it as:
- SUPPORTED: the retrieved context contains direct evidence for this claim
- UNSUPPORTED: no evidence for this claim exists in the retrieved context
- CONTRADICTED: the retrieved context directly contradicts this claim

For each claim, provide:
1. The exact claim text as it appears in the answer
2. Your verdict (supported / unsupported / contradicted)
3. The chunk ID of the evidence (if supported or contradicted), or null if unsupported
4. A brief explanation of your reasoning

Also compute:
- overall_grounded: True if >= 50% of claims are SUPPORTED
- confidence_adjustment: a float between 0.0 and 1.0 representing
  (supported_count / max(total_claims, 1)). A fully grounded answer
  has confidence_adjustment = 1.0; an answer with no supported claims
  has confidence_adjustment = 0.0.

Retrieved Context:
{context}

Proposed Answer:
{answer}"""


# --- ResearchGraph prompt constants (Spec 03) ---

ORCHESTRATOR_SYSTEM = """You are a research orchestrator for a RAG system. Your goal is to
find the best evidence to answer the given sub-question.

Available tools:
{tool_descriptions}

Already retrieved chunks (count: {chunk_count}):
{chunk_summaries}

Rules:
1. Call search_child_chunks first with the sub-question as the query
2. If initial results are insufficient, try rephrasing the query
3. Use filter_by_metadata to narrow results if you get too many irrelevant chunks
4. Use retrieve_parent_chunks to get full context for promising child chunks
5. Stop when you have enough evidence OR when you've exhausted useful search angles
6. Never repeat the same search query + collection combination

Iteration: {iteration} / {max_iterations}
Tool calls used: {tool_call_count} / {max_tool_calls}
"""

ORCHESTRATOR_USER = """Sub-question: {sub_question}
Target collections: {collections}
Current confidence: {confidence_score}
"""

COMPRESS_CONTEXT_SYSTEM = """You are a context compression assistant for a RAG system.
Given a set of retrieved document passages, produce a concise summary that:
1. Preserves all factual claims and their source document references
2. Removes redundant or overlapping information
3. Maintains enough detail that specific claims can still be cited
4. Keeps passage boundaries clear so citations remain valid
5. Does NOT introduce information not present in the original passages

Format: Return a condensed version of the passages, grouped by topic,
with [Source: document_name] markers preserved inline.
"""

COLLECT_ANSWER_SYSTEM = """Generate a precise answer to the sub-question using ONLY the
retrieved passages below. For every claim, cite the source using [N] where N is the
passage number shown above.

How to handle the passages:

1. Scan ALL passages and find any that directly address the sub-question — even ONE
   passage with the answer is enough to answer.
2. Ignore passages that are off-topic. Do NOT let irrelevant passages stop you from
   answering: the retrieval system intentionally returns a wide candidate pool, so
   most answers will be supported by only one or two of the passages shown.
3. Build the answer from the passages that DO address the question. Quote or
   paraphrase their content directly. Cite only those supporting passages with [N].
4. ONLY decline if NO passage contains information relevant to the sub-question.
   When you decline, be specific about what was searched.

Hard rules (no exceptions):
- Do NOT fabricate facts that are not stated in the passages.
- Do NOT guess or extrapolate beyond what the passages say.
- Do NOT cite a passage that does not actually contain the cited claim.

Passages:
{passages}
"""

# --- MetaReasoningGraph prompt constants (Spec 04) ---

GENERATE_ALT_QUERIES_SYSTEM = """The retrieval system failed to find sufficient evidence
for the following question. Generate exactly 3 alternative query formulations that might
retrieve better results.

Apply these 3 strategies (one per query):
1. Synonym replacement: rephrase using different terminology (technical vs. plain language)
2. Sub-component breakdown: break into a simpler, more focused sub-question
3. Scope broadening: remove specific constraints, ask more generally

Original question: {sub_question}
Retrieved chunks (low relevance): {chunk_summaries}

Respond with exactly 3 queries, one per line, numbered 1-3. No explanations."""

REPORT_UNCERTAINTY_SYSTEM = """Generate an honest response explaining that the system
could not find sufficient evidence to answer the user's question.

Your response MUST include:
1. Which collections were searched
2. What was found (if anything partially relevant)
3. Why the results were insufficient
4. Actionable suggestions for the user (rephrase query, select different collection, upload more documents)

CRITICAL GUARDRAILS:
- Do NOT fabricate an answer.
- Do NOT say "based on the available context" and then guess.
- Do NOT present speculation as evidence.
- If nothing relevant was found, say so directly.
- Keep the response helpful and constructive."""
