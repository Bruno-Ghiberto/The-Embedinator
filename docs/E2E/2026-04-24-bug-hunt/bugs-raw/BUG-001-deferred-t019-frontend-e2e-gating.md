# BUG-001: T019 frontend-e2e CI gate flip deferred (workflow SC-003 e2e times out on CI ollama)

**Severity**: Minor
**Layer**: ci/workflow + tests/e2e
**Discovered**: 2026-04-27 ~23:30 UTC (initial filing); empirically validated 2026-04-28 ~00:27 UTC (CI run)

> **REVISION 2026-04-28** — The original hypothesis (compose-up would time out on GPU-less CI) was **WRONG**. Empirical CI evidence proved the stack comes up fine in 4m49s (CPU ollama works, just slowly). The actual failure is one test, not the gate infrastructure. Original "Steps to Reproduce" / "Expected" / "Actual" sections updated below; original "Root-cause hypothesis" superseded.

## Steps to Reproduce

1. Open `.github/workflows/_ci-core.yml` and locate the `frontend-e2e` job (lines 270-325).
2. Note the `continue-on-error: true` at line 279 (the gate flag spec-28 manual T019 wants flipped).
3. Run a CI build with the current Wave 1 stabilization changes (PR #62, run 25026770726).
4. Observe: stack comes up in ~4m49s (all 4 containers healthy), Playwright runs, **1 test fails**: `workflow.spec.ts:7 — SC-003 end-to-end workflow: create collection → upload → chat`. Other 25 tests (5 chat + 4 collections + 3 documents + 4 settings + 10 responsive) pass.
5. With `continue-on-error: true`, the failure is non-blocking. Flip to `false` → 1 test failure blocks every PR merge.

## Expected

After Wave 1 stabilization, flipping `continue-on-error: false` should make the `frontend-e2e` job a real merge gate (per spec-28 SC-001 / US1, FR-002, AC-004). All 26 tests should pass on CI as they do locally (postwave: 26 / 0 in 5.0s).

## Actual

CI run 25026770726, job 73299511270 — frontend-e2e:
- Stack came up fine: qdrant Healthy 00:25:28, ollama Healthy 00:25:33, backend Healthy 00:25:44, frontend Healthy 00:25:50. Total: 4m49s.
- `npm run test:e2e` ran for ~73s (00:25:50 → 00:27:03).
- **1 of 26 tests failed**: `[chromium] tests/e2e/workflow.spec.ts:7:5 SC-003 end-to-end workflow: create collection → upload → chat`. Failure: `expect(locator).toBeVisible() failed — element(s) not found`. Test artifact under `test-results/workflow-SC-003-end-to-end-0a526--collection-→-upload-→-chat-chromium/`.
- Process exit 1 → job marked `fail` → `continue-on-error: true` saves it from blocking the PR.

## Root-cause hypothesis

`workflow.spec.ts` SC-003 is the only test in the suite that exercises the **real** backend (no `page.route` mocks). It chains: create collection → upload PDF → chat → assert assistant response visible. The test passes locally in 5.0s because the dev machine has GPU-accelerated ollama and warm caches. On CI runners ollama runs CPU-only — model loads + first-token-latency + full-response generation easily exceeds the test's 120s `setTimeout` for a real chat round-trip. The "element not found" error is most likely the assistant-message `.prose-sm` selector waiting for chat output that never arrives within the timeout.

The original hypothesis (compose-up failure on GPU-less runners) was empirically falsified. CI runners run ollama CPU-only successfully — just slowly enough that any real-stack test will be flaky.

## Artifacts

- CI run: https://github.com/Bruno-Ghiberto/The-Embedinator/actions/runs/25026770726
- Failing job: https://github.com/Bruno-Ghiberto/The-Embedinator/actions/runs/25026770726/job/73299511270
- Test path: `frontend/tests/e2e/workflow.spec.ts:7`
- Local postwave: 26/0 in 5.0s — `docs/E2E/2026-04-24-bug-hunt/logs/playwright-postwave.log`
- Engram: `spec-28/wave1-playwright-fixes`, `spec-28/playwright-baseline`

## Resolution path (proposed for follow-up PR)

Pick ONE of:

**A. Skip SC-003 in CI** (smallest change, ships fastest):
1. Add `test.skip(!!process.env.CI, "SC-003 needs GPU-class backend; tracked by BUG-001")` at the top of `workflow.spec.ts:7`.
2. Document that SC-003 must be run locally before merge.
3. Flip `continue-on-error: true → false` on `frontend-e2e`.
4. CI gate now blocks on the 25 mocked tests, which all pass.

**B. Mock SC-003** (most consistent — same pattern as other 25 tests):
1. Convert SC-003 to use `page.route` mocks like the other 25 tests.
2. Loses real-stack assurance for SC-003 (was its purpose) — would need a separate non-CI smoke test.
3. Flip `continue-on-error: true → false`.

**C. Add GPU CI runner for SC-003 only**:
1. Provision a GPU-enabled CI runner (cost / complexity).
2. Split `frontend-e2e` into `frontend-e2e-mocked` (current runners, 25 tests) + `frontend-e2e-real` (GPU runner, SC-003 only).
3. Flip both jobs to gating.

**Recommendation**: A. The SC-003 test's real-stack value is preserved (still runs locally, still in the test file), and the gate flip ships immediately. Option B is cleaner long-term but throws away the only real-stack regression check we have. Option C is over-engineering for one test.
