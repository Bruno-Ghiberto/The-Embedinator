# ADR-008: Multi-Provider LLM Architecture

**Status**: Accepted
**Date**: 2026-03-03
**Decision Makers**: Architecture Team

## Context

Ollama is the default inference engine — it runs locally with zero cloud dependencies. However, local inference requires hardware: not everyone has 32 GB of RAM or a GPU. The system needs to support cloud LLM providers as an alternative without compromising the privacy-by-default design.

## Decision

Implement a **Provider Registry** pattern with pluggable LLM/embedding providers:
- **Ollama** (default, no key needed) — local inference
- **OpenRouter** (recommended cloud option) — one API key, 200+ models
- **OpenAI** (direct) — for users with existing OpenAI accounts
- **Anthropic** (direct) — for Claude model access

API keys are encrypted with **Fernet** at rest in SQLite.

## Rationale

1. **Privacy by default**: Ollama is the default; cloud providers are strictly opt-in
2. **OpenRouter as primary cloud**: One key unlocks 200+ models (Claude, GPT, Llama, Mixtral, Gemini, DeepSeek); pay-as-you-go with no monthly commitment
3. **Encrypted key storage**: Fernet symmetric encryption prevents plaintext keys in the database
4. **Per-conversation switching**: Users can select provider and model per chat session via the UI
5. **Thin adapter pattern**: Each provider implements `LLMProvider` ABC — adding new providers is a single class

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| Ollama only | Excludes users without GPU hardware |
| LiteLLM unified proxy | Adds another dependency and process; provider adapters are simple enough to implement directly |
| Environment-variable-only keys | No encryption at rest; no UI management |

## Consequences

### Positive
- System works for both GPU-equipped and cloud-only users
- Model dropdown auto-populates from all active providers
- Key management through UI (Provider Hub in /settings)

### Negative
- Multiple provider adapters to maintain
- Cloud providers introduce latency variability and cost
- Fernet key management adds a security surface (key must be in `.env`)
