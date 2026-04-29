# BUG-004: HuggingFace DNS resolution failure on cross-encoder startup

- **Severity**: Minor
- **Layer**: Infrastructure
- **Discovered**: 2026-04-28 14:34 UTC via Log scan (A5 historical log tail — events dated 2026-04-14, not live)

## Steps to Reproduce

1. Start the backend container in an environment with intermittent or absent external DNS resolution (e.g., network blip, cold-start before DNS cache warms, or restricted outbound access).
2. The backend's lifespan startup attempts to load the cross-encoder model `cross-encoder/ms-marco-MiniLM-L-6-v2` from HuggingFace Hub.
3. If DNS resolution for `huggingface.co` fails at the moment `HEAD https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2/resolve/main/adapter_config.json` is issued, the backend logs `Application startup failed. Exiting.` and the container exits.

## Expected

Backend startup either (a) loads the cross-encoder from a pre-cached local copy without making an outbound HTTP request, or (b) catches the DNS resolution error, logs a warning, and continues startup with cross-encoder reranking disabled (graceful degradation), or (c) retries the DNS resolution with a timeout before failing hard.

## Actual

Two occurrences on 2026-04-14: `'[Errno -3] Temporary failure in name resolution' thrown while requesting HEAD https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2/resolve/main/adapter_config.json` — backend logs `ERROR: Application startup failed. Exiting.` and the container exits entirely. Recovery requires a Docker restart (`docker compose up -d backend`). This is NOT a live issue today (stack has been healthy 90+ min at Live Block start).

## Artifacts

- Log excerpt:
  ```
  '[Errno -3] Temporary failure in name resolution' thrown while requesting HEAD
  https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2/resolve/main/adapter_config.json
  ERROR: Application startup failed. Exiting.
  ```
- Date of occurrences: 2026-04-14 (two occurrences, backend recovered on manual restart)
- Source: A5 historical log scan during pre-session tail
- File ref: `backend/main.py` lifespan startup — cross-encoder model load; `backend/retrieval/reranker.py` model initialization

## Root-cause hypothesis

HuggingFace Hub's `cached_download` / model-loading code issues a `HEAD` request to check for model updates even when a local cache exists. If the DNS resolver returns `NXDOMAIN` or times out before TCP connects, the library raises `ConnectionError` which is not caught by the backend's lifespan handler — causing a hard exit rather than graceful degradation. Fix options: (a) pre-pull the model into the Docker image (`RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"` in Dockerfile.backend) so no outbound call is needed at runtime; (b) wrap the model load in a try/except with graceful-degradation fallback disabling reranking; (c) set `TRANSFORMERS_OFFLINE=1` env var to prevent outbound Hub checks entirely.
