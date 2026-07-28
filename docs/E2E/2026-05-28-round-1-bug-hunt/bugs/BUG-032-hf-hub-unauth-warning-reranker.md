# BUG-032: HuggingFace Hub unauthenticated-request warning on reranker load each cold start

- **Severity**: COSMETIC
- **Layer**: Backend
- **Discovered**: 2026-06-10T21:46:49Z in Phase 1 (P1-S1)
- **Phase scenario**: P1-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Perform a cold start (`docker compose up -d`)
2. Read backend startup logs
3. Observe HuggingFace Hub unauthenticated-request warning during reranker model load

## Expected
Backend starts without HuggingFace Hub authentication warnings; reranker loads cleanly from local cache with no network-access noise.

## Actual
A HuggingFace Hub unauthenticated-request warning is emitted on each cold start during reranker load; model loads correctly from local cache today but the warning persists every boot.

## Artifacts
- Screenshot: null
- Log excerpt: logs/P1-S1-startup-warnings.log (gitignored)
- Trace: null

## Root-cause hypothesis
The HF Hub client attempts to validate the cached model against the Hub registry on each startup without an auth token configured; setting `HUGGINGFACE_HUB_OFFLINE=1` or providing a `HF_TOKEN` environment variable would suppress the network probe and eliminate the warning.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Reporter: log-analyst. Rate-limit risk only if the Docker image is rebuilt and the model must re-download from Hub. No functional impact under normal operation (local cache hit).
