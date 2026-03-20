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
| `{name}.status`   | One line: RUNNING, PASSED, FAILED, ERROR    |
| `{name}.summary`  | ~20-line summary with counts and failures   |
| `{name}.log`      | Full pytest output (search only, do not cat)|

**Features:**

- Automatic virtual environment creation and dependency management
- Dependency hash tracking (reinstalls only when requirements change)
- Atomic status file writes (safe for polling)
- Token-efficient summary generation for AI agent consumption

### run-test-external.txt

Reference notes and documentation for the test runner script.
