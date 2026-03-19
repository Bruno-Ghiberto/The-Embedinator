# A4: Regression + Acceptance Criteria Verification

**Agent type**: `quality-engineer`
**Model**: **Sonnet 4.6** (`model="sonnet"`)

You run the full regression suite and verify all 11 acceptance criteria for spec-13. You are the final quality gate before the spec is considered complete.

## Assigned Tasks

T024-T027 from `specs/013-security-hardening/tasks.md` (Phase 6: Polish and Cross-Cutting Concerns).

| Task | Description |
|------|-------------|
| T024 | Run full regression suite via `zsh scripts/run-tests-external.sh -n spec13-full tests/` -- all new tests pass, pre-existing failure count unchanged at 39 |
| T025 | Verify all 11 acceptance criteria from quickstart.md (AC-1 through AC-11) |
| T026 | Verify SC-007: no new dependencies added to `requirements.txt` |
| T027 | Verify FR-008: existing security behaviors (extension allowlist, file size limit, rate limiting, CORS, collection name validation) all function identically |

## Source Documents to Read

Read these files in order before starting any work:

1. `Docs/PROMPTS/spec-13-security/13-implement.md` -- read the "Acceptance Criteria Verification Checklist" section
2. `specs/013-security-hardening/quickstart.md` -- the 11 acceptance criteria (AC-1 through AC-11)
3. `specs/013-security-hardening/spec.md` -- 8 FRs and 7 SCs (especially FR-008 and SC-006)
4. `specs/013-security-hardening/data-model.md` -- the 11-step ingest operation order to verify
5. `Docs/Tests/spec13-a1-audit.md` -- A1's baseline audit (pre-existing failure count)
6. `Docs/Tests/spec13-a2.summary` -- A2's test results
7. `Docs/Tests/spec13-a3.summary` -- A3's test results

## Step 1: Full Regression Suite

Run the full test suite:
```bash
zsh scripts/run-tests-external.sh -n spec13-full tests/
```

Poll until complete:
```bash
cat Docs/Tests/spec13-full.status
```

Read results:
```bash
cat Docs/Tests/spec13-full.summary
```

**Expected outcome**: All new security tests pass. Pre-existing failure count remains at exactly 39. Any increase is a regression that MUST be investigated and fixed before continuing.

## Step 2: Verify All 11 Acceptance Criteria

For each AC, use Serena MCP (`find_symbol` with `include_body=true`) to read the relevant code and/or inspect test results.

| AC | Description | How to Verify |
|----|-------------|---------------|
| AC-1 | 15,000-char message processed; stored query is 10,000 chars | Read `test_chat_security.py` -- confirm a test exists for 15k-char input with assertion on 10k truncation. Read `chat.py` `generate()` -- confirm `message = body.message[:10_000]` is present. |
| AC-2 | `_build_filter({"arbitrary_field": "x"})` returns `None` | Read `test_searcher_security.py` -- confirm test for all-unknown-keys returning `None`. Read `searcher.py` `_build_filter()` -- confirm the `if key not in ALLOWED_FILTER_KEYS: continue` guard exists. |
| AC-3 | File named `../../etc/passwd.txt` is sanitized | Read `test_ingest_security.py` -- confirm test for path traversal sanitization. Read `ingest.py` -- confirm `_sanitize_filename` is called on the filename assignment. |
| AC-4 | `.pdf` with wrong magic bytes returns HTTP 400 `FILE_CONTENT_MISMATCH` | Read `test_ingest_security.py` -- confirm test for forged PDF rejection. Read `ingest.py` -- confirm `content[:4] != b"%PDF"` check exists after size validation. |
| AC-5 | `.md` with any content succeeds (no magic check) | Read `test_ingest_security.py` -- confirm test for non-PDF file passing without magic check. Read `ingest.py` -- confirm the magic check is guarded by `if suffix == ".pdf"`. |
| AC-6 | Log event with `api_key` field shows `[REDACTED]` | Read `test_main_security.py` -- confirm test for api_key redaction. Read `main.py` -- confirm `_strip_sensitive_fields` function exists and is in the processor chain. |
| AC-7 | `GET /api/providers` has `has_key`, no `api_key_encrypted` | Read `test_providers_security.py` -- confirm both assertions exist. Read `providers.py` `list_providers()` -- confirm serialization via `ProviderDetailResponse.model_dump()`. If no test file exists for this, create `tests/unit/api/test_providers_security.py` with ~2 tests. |
| AC-8 | Upload `.exe` returns HTTP 400 `FILE_FORMAT_NOT_SUPPORTED` | Read `ingest.py` -- confirm `ALLOWED_EXTENSIONS` set does not include `.exe`. Check test results for any existing extension validation test. |
| AC-9 | Upload >100 MB returns HTTP 413 `FILE_TOO_LARGE` | Read `ingest.py` -- confirm size check against `settings.max_upload_size_mb` exists. Check test results for existing size validation test. |
| AC-10 | 31 chat requests/60s returns HTTP 429 | Read `backend/middleware.py` -- confirm `RateLimitMiddleware` is present. Check test results for existing rate limit tests. |
| AC-11 | `_strip_sensitive_fields` at index -2 in processor chain | Read `test_main_security.py` -- confirm a test for processor chain position exists. Read `main.py` `_configure_logging()` -- confirm `_strip_sensitive_fields` is the entry immediately before `JSONRenderer`. |

## Step 3: Verify SC-007 (No New Dependencies)

Read `requirements.txt` and confirm no new packages were added. The only new import in any production file should be `import re as _re` in `ingest.py`, which is stdlib.

## Step 4: Verify FR-008 (Existing Security Preserved)

Verify via code inspection and test results that these existing behaviors are unchanged:
- Extension allowlist in `ingest.py` (`ALLOWED_EXTENSIONS` set)
- File size limit in `ingest.py` (size check against `settings.max_upload_size_mb`)
- Rate limiting in `middleware.py` (`RateLimitMiddleware`)
- CORS in `main.py` (`CORSMiddleware` registration)
- Collection name validation in `collections.py`

## Step 5: Verify Ingest Operation Order

Read `backend/api/ingest.py` `ingest_file()` and verify the operation order matches the 11-step sequence from `data-model.md`:

```
1.  Extension check
2.  Read content
3.  Size check
4.  PDF magic byte check (NEW)
5.  Collection verify
6.  Sanitize filename (NEW)
7.  Save file
8.  Hash + dedup
9.  Changed-file check
10. Create records
11. Launch ingestion
```

## Step 6: Verify chat.py Message References

Read `backend/api/chat.py` `generate()` and confirm:
- `message = body.message[:10_000]` exists before `initial_state`
- `HumanMessage(content=message)` (not `body.message`)
- `query=message` in `db.create_query_trace(...)` (not `body.message`)
- No remaining references to `body.message` after the truncation assignment (within `generate()`)

## Output

Write the final report to `Docs/Tests/spec13-a4-final.md` with:

### Report Structure

1. **Regression Results**: Total tests, passed, failed, pre-existing failure count
2. **Acceptance Criteria Table**: One row per AC with PASS/FAIL verdict and evidence
3. **SC-007 Verification**: Confirm no new dependencies
4. **FR-008 Verification**: Confirm all existing security behaviors intact
5. **Operation Order Verification**: Confirm 11-step ingest sequence
6. **New Test Count**: Total new tests added by spec-13
7. **Overall Verdict**: PASS (all 11 ACs pass, no regressions) or FAIL (with details)

## Key Constraints

- **NEVER run pytest directly** -- use `zsh scripts/run-tests-external.sh -n <name> <target>`
- **Pre-existing failures: 39** -- the count from A1's baseline report. Any increase is a regression.
- **Use Serena MCP** for all code reading (`find_symbol`, `get_symbols_overview`)
- **If AC-7 tests are missing**: A3 was assigned T020 to create `test_providers_security.py`. If the file does not exist, create it yourself with ~2 tests before proceeding.
- **Do NOT modify production files** unless you find a regression that must be fixed. If a fix is needed, document it clearly in the report.

## Success Criteria

- `Docs/Tests/spec13-full.status` is `PASSED`
- All 11 acceptance criteria verified with PASS verdict
- Pre-existing failure count remains at 39
- No new dependencies in `requirements.txt`
- Final report written to `Docs/Tests/spec13-a4-final.md`
- Overall verdict is PASS

## After Completing All Tasks

Report completion to the orchestrator. The orchestrator will read your final report and close the spec-13 implementation.
