# A2 — Wave 2 — python-expert (Sonnet)

## Role

You are a Wave 2 python-expert running in parallel with A3. You own `backend/config.py` and `.env.example`. You run after Wave 1 completes (orchestrator will signal this). Do not start until you receive the Wave 1 gate-passed signal.

## Read First

1. `specs/017-infra-setup/tasks.md` — canonical task list
2. `Docs/PROMPTS/spec-17-infra/17-implement.md` — authoritative code specs (especially the `backend/config.py` and `.env.example` sections)

Then await the orchestrator signal that Wave 1 baseline run completed without error.

## Assigned Tasks

T030–T035.

## T030 — Fix `api_key_encryption_secret` alias (Constitution V)

Read `/home/brunoghiberto/Documents/Projects/The-Embedinator/backend/config.py`.

Current line 31:
```python
api_key_encryption_secret: str = ""
```

Replace it with:
```python
api_key_encryption_secret: str = Field(default="", alias="EMBEDINATOR_FERNET_KEY")  # Constitution V
```

The `from pydantic import Field` import is already present on line 3 — do not add a duplicate.

## T031 — Verify `model_config` includes `populate_by_name=True`

Read the current `model_config` line (currently line 79):
```python
model_config = SettingsConfigDict(env_file=".env")
```

Replace with:
```python
model_config = SettingsConfigDict(env_file=".env", populate_by_name=True)
```

`populate_by_name=True` is required when any field uses `alias=`. Without it, code that accesses `settings.api_key_encryption_secret` by its Python attribute name will fail at runtime with pydantic-settings >= 2.x.

## T032 — Verify `confidence_threshold` is integer

Confirm `confidence_threshold: int = 60` is present. This field should already be correct at post-spec-16 state. If you find `float = 0.6`, correct it to `int = 60`.

Do not change anything else on this line.

## T033 — Verify all spec-04/10/15 fields are present

Confirm each of the following fields exists with the correct type and default. If any are missing, add them in the correct section.

| Field | Section | Expected |
|-------|---------|---------|
| `log_level_overrides` | Server | `str = Field(default="", alias="LOG_LEVEL_OVERRIDES")` |
| `frontend_port` | Frontend | `int = 3000` |
| `compression_threshold` | Agent | `float = 0.75` |
| `meta_relevance_threshold` | Agent | `float = 0.2` |
| `meta_variance_threshold` | Agent | `float = 0.15` |
| `rate_limit_provider_keys_per_minute` | Rate Limiting | `int = 5` |
| `rate_limit_general_per_minute` | Rate Limiting | `int = 120` |

If `rate_limit_default_per_minute` is present, rename it to `rate_limit_general_per_minute`. Do not leave both names in the file.

## T034 — Rewrite `.env.example` to document all 28 Settings fields

Read the current `.env.example`. Compare against the 28-field Settings class.

Rewrite the file using the complete template in `Docs/PROMPTS/spec-17-infra/17-implement.md` (the `.env.example` section). Every Settings field must appear with:
- The correct uppercase env var name
- A `# FIELD_NAME — description. Expected: type. Default: value.` comment above it
- The correct default value

Critical requirements:
- `EMBEDINATOR_FERNET_KEY=` not `API_KEY_ENCRYPTION_SECRET=`
- `CONFIDENCE_THRESHOLD=60` not `0.6`
- `DEFAULT_LLM_MODEL=qwen2.5:7b` not `llama3.2`
- `RATE_LIMIT_GENERAL_PER_MINUTE=120` not `RATE_LIMIT_DEFAULT_PER_MINUTE=120`
- All spec-04 fields: `META_RELEVANCE_THRESHOLD`, `META_VARIANCE_THRESHOLD`
- All spec-10 fields: `RATE_LIMIT_PROVIDER_KEYS_PER_MINUTE`
- All spec-15 fields: `LOG_LEVEL_OVERRIDES`, `FRONTEND_PORT`

## T035 — Gate Check: config tests

Run:
```
zsh scripts/run-tests-external.sh -n spec17-config --no-cov tests/unit/test_config.py
```

Poll `cat Docs/Tests/spec17-config.status` until `done` or `error`.

Read `cat Docs/Tests/spec17-config.summary`.

Acceptance: failure count must not exceed 1 (one pre-existing failure is known for this file). If failures exceed 1, read `Docs/Tests/spec17-config.log` and diagnose before proceeding.

Report result to orchestrator: "A2 complete. T030–T035 done. Config gate: X failures (acceptable threshold: 1)."

---

## Critical Gotchas

- NEVER run pytest directly. Always use `zsh scripts/run-tests-external.sh -n <name> <target>`.
- `populate_by_name=True` is required in `model_config` — without it, attribute-name access breaks for aliased fields.
- Do not rename `api_key_encryption_secret` (the Python attribute name). Only add the `alias=` argument. Other code accesses `settings.api_key_encryption_secret` by the Python name.
- Do not add `from pydantic import Field` — it is already present.
- Do not modify any field that is already correct. Make only the two targeted changes: the `api_key_encryption_secret` line and the `model_config` line.
- `rate_limit_general_per_minute` is the correct name. `rate_limit_default_per_minute` is stale — rename if found.
