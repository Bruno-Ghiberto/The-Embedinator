# scripts/

Development and automation scripts.

## Available Scripts

### run-tests-external.sh

Detached test runner that executes pytest outside the current process and
writes results to files. Designed for CI pipelines and agent-driven
workflows where streaming test output to stdout is impractical.

**Execution Modes:**

| Mode         | Flag        | Description                              |
|--------------|-------------|------------------------------------------|
| Detached     | (default)   | Invisible background process             |
| Visible      | `--visible` | Opens a new tmux pane for live output    |
| Foreground   | `--fg`      | Runs in the current terminal (blocking)  |

**Usage:**

```bash
# Background (returns immediately)
zsh scripts/run-tests-external.sh -n myrun tests/

# Visible in tmux
zsh scripts/run-tests-external.sh --visible -n myrun tests/

# Foreground (blocking)
zsh scripts/run-tests-external.sh --fg tests/unit/
```

**Options:**

| Flag               | Description                                 |
|--------------------|---------------------------------------------|
| `-n, --name NAME`  | Run identifier (default: timestamp)         |
| `-m, --markers`    | Pytest marker expression                    |
| `-k, --filter`     | Pytest -k name filter                       |
| `--no-cov`         | Disable coverage collection                 |
| `--fail-fast`      | Stop on first failure                       |
| `--quiet`          | Minimal output                              |
| `-h, --help`       | Show full help                              |

**Output Files** (in `Docs/Tests/`):

| File              | Content                                     |
|-------------------|---------------------------------------------|
| `{name}.status`   | One line: RUNNING, PASSED, FAILED, ERROR, INTERRUPTED, NO_TESTS |
| `{name}.summary`  | ~20-line summary with counts and failures   |
| `{name}.log`      | Full pytest output (search only, do not cat)|

`PASSED` means every test that ran passed. It is also written when pytest exited 1
only because `--cov-fail-under` was not met (`scripts/lib/coverage-gate.sh`);
coverage is a separate gate.

**Features:**

- Automatic virtual environment creation and dependency management
- Dependency hash tracking (reinstalls only when requirements change)
- Atomic status file writes (safe for polling)
- Token-efficient summary generation for AI agent consumption

### gate-baseline.sh

Deterministic verdict for one run written by `run-tests-external.sh`. Encodes the
campaign rule — zero failures and zero errors, never a pass count — so nobody has to
read a `.summary` and judge it.

```bash
scripts/gate-baseline.sh s31-b2-baseline
# GATE s31-b2-baseline: GREEN passed=1553 skipped=34 xfailed=45 xpassed=16 failed=0 errors=0 status=PASSED
```

| Exit | Verdict      | Meaning                                                              |
|------|--------------|----------------------------------------------------------------------|
| 0    | `GREEN`      | status `PASSED` and `failed=0 errors=0` on the pytest result line    |
| 1    | `RED`        | any failed/error count, or a finished status other than `PASSED`; counts outvote the status word |
| 2    | `NO-VERDICT` | no run name, missing `.status`/`.summary`, status `RUNNING`, or no pytest result line — fails closed |

The reason is printed to stderr whenever the verdict is not `GREEN`. Optional second
argument: the output directory (default `Docs/Tests/`). Behaviour tests:
`bash scripts/test-gate-baseline.sh`.

### check-all.sh

Runs the four deterministic gates every candidate must clear before review, reports
each one, and exits with the verdict. Backend pytest is not included — it runs only
through `run-tests-external.sh` and is judged by `gate-baseline.sh`.

```bash
scripts/check-all.sh
#   pre-commit  PASS
#   typecheck   PASS
#   lint        PASS
#   vitest      PASS
# check-all: ALL GREEN (4 gates)
```

| Gate         | Command                        | Runs in     |
|--------------|--------------------------------|-------------|
| `pre-commit` | `pre-commit run --all-files`   | repo root   |
| `typecheck`  | `npm run typecheck`            | `frontend/` |
| `lint`       | `npm run lint`                 | `frontend/` |
| `vitest`     | `npm test`                     | `frontend/` |

`pre-commit` runs first because it is the only gate that may rewrite files. Exit 0 =
all green, 1 = at least one gate failed (each FAIL is named and the last 25 log lines
are echoed), 2 = `NO-VERDICT` (missing `frontend/package.json` or a tool on PATH;
nothing runs). Full per-gate output: `Docs/Tests/check-all/<gate>.log`. Behaviour
tests: `bash scripts/test-check-all.sh`.

### run-test-external.txt

Reference notes and documentation for the test runner script.
