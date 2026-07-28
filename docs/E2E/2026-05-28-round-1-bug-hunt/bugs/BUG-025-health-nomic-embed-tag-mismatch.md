# BUG-025: /api/health reports nomic-embed-text=false — :latest tag suffix unnormalized

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-06-10T21:46:49Z in Phase 1 (P1-S1)
- **Phase scenario**: P1-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Start the stack (`docker compose up -d`)
2. Run `curl localhost:8000/api/health` — observe `"nomic-embed-text": false` in the models section
3. Run `curl localhost:11434/api/tags` — observe `nomic-embed-text:latest` (261 MB) listed as installed

## Expected
`/api/health` models section shows `"nomic-embed-text": true` when the model is installed and accessible via Ollama.

## Actual
`/api/health` reports `"nomic-embed-text": false` on every boot despite the model being present as `nomic-embed-text:latest`; the health check does not normalize the `:latest` tag suffix before comparison.

## Artifacts
- Screenshot: null
- Log excerpt: logs/P1-S1-startup-warnings.log (gitignored)
- Trace: null

## Root-cause hypothesis
The health check string-compares the configured short name ("nomic-embed-text") against the Ollama `/api/tags` list entries which include the ":latest" tag suffix; without normalization (strip `:tag` before comparison), the match always fails.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Reporter: log-analyst. Embeddings continue to work correctly — Ollama resolves short names at inference time. Health surface is permanently misleading. Related to BUG-026 (aggregate health stays "healthy" despite this false flag).

P3-S1 confirmation (2026-06-18): /api/health still reports {"nomic-embed-text": false} after develop merge (5fac6e5) + backend rebuild. nomic-embed-text:latest (0.27 GB) confirmed present in Ollama via /api/tags. qwen3:14b reports healthy because it uses an explicit tag; bare short-name models do not match. Bug persists across P1→P3.
