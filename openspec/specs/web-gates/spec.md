# Web Gates Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## MODIFIED Requirements

### Requirement: E2E baseline regeneration is serialized by a file lock
The `_get_or_create_e2e_baseline` function SHALL acquire an exclusive file lock (`fcntl.flock(LOCK_EX)`) on a sidecar `.lock` file next to `e2e-baseline.json` before regenerating the cache. After acquiring the lock, it SHALL re-check whether another caller has already regenerated for the current `main_sha`; if so, it SHALL return that cached result without running the e2e suite a second time. The cache file SHALL be written via atomic temp-file-plus-rename so a crashed writer cannot leave a partial JSON.

#### Scenario: Peer has regenerated while we waited for the lock
- **GIVEN** two concurrent callers both discover a stale `e2e-baseline.json`
- **WHEN** caller A acquires the lock first and regenerates the cache for `main_sha = Y`
- **AND** caller B acquires the lock after A releases it
- **THEN** caller B SHALL re-read the cache file, see `main_sha = Y`, and return that result
- **AND** caller B SHALL NOT call `run_command` to regenerate

#### Scenario: Writer crashes mid-write
- **GIVEN** a regeneration in progress that writes to a temp file
- **WHEN** the process dies after creating the temp file but before `os.rename`
- **THEN** `e2e-baseline.json` on disk SHALL be either the previous cached content or absent — never a partial write

### Requirement: E2E baseline run uses a dedicated port
The `run_command` call inside `_get_or_create_e2e_baseline` SHALL pass an explicit `env` dict containing `PW_PORT = str(_E2E_BASELINE_PORT)` so the baseline dev server never collides with a worktree dev server. `_E2E_BASELINE_PORT` SHALL be `3199` (a module-level constant).

#### Scenario: Baseline run uses dedicated port
- **WHEN** `_get_or_create_e2e_baseline` invokes `run_command` to regenerate the cache
- **THEN** the `env` argument SHALL include `PW_PORT = "3199"`
- **AND** if the current profile exposes `e2e_gate_env(3199)`, its keys SHALL be merged into the env dict

#### Scenario: Parent environment PW_PORT is shadowed
- **GIVEN** the parent process has `PW_PORT = "3105"` in its environment (from a prior worktree)
- **WHEN** the baseline run executes
- **THEN** the subprocess SHALL see `PW_PORT = "3199"`, not `3105`

### Requirement: Dirty project root skips cache persistence
Before regenerating the baseline, the function SHALL check whether `project_root` has uncommitted changes (via `git status --porcelain`). If the output is non-empty, the baseline SHALL still be computed in-memory but SHALL NOT be written to disk. The returned dict SHALL include `"cacheable": False`.

#### Scenario: Clean main, cache persisted
- **GIVEN** `git status --porcelain` on `project_root` returns empty
- **WHEN** the baseline regenerates
- **THEN** the cache is written to `e2e-baseline.json`
- **AND** the returned dict has `"cacheable": True` (or omitted — defaults to True)

#### Scenario: Dirty main, cache skipped
- **GIVEN** `git status --porcelain` on `project_root` returns one or more modified files
- **WHEN** the baseline regenerates
- **THEN** the cache file is NOT written
- **AND** a WARNING is logged containing the phrase "dirty project root"
- **AND** the returned dict has `"cacheable": False`

### Requirement: Unreliable main detection fails closed
`execute_e2e_gate` SHALL delegate main-worktree detection to `_detect_main_worktree(wt_path)` which returns `None` when git calls fail or the detected directory does not look like a git repository. When detection returns `None`, the gate SHALL skip baseline comparison entirely and treat every entry in `wt_failures` as a new failure.

#### Scenario: Git rev-parse fails
- **GIVEN** `run_git("rev-parse", "--show-toplevel", cwd=wt_path)` returns a non-zero exit code
- **WHEN** `execute_e2e_gate` processes a failing run
- **THEN** `_detect_main_worktree` returns `None`
- **AND** `_get_or_create_e2e_baseline` is NOT called
- **AND** the gate returns `status="fail"` with ALL `wt_failures` in the "new failures" header

#### Scenario: Git worktree list returns no main
- **GIVEN** `rev-parse --show-toplevel` succeeds but `worktree list --porcelain` has no line other than the current worktree
- **WHEN** detection runs
- **THEN** `_detect_main_worktree` returns `None`

#### Scenario: Detected directory has no .git entry
- **GIVEN** `_detect_main_worktree` walks to a candidate directory that does not contain `.git`
- **THEN** the function returns `None` rather than the candidate path

### Requirement: Existing cache files remain compatible
On first regeneration after the upgrade, the sidecar `.lock` file SHALL be created next to any existing `e2e-baseline.json`. Old caches SHALL continue to be honored via their `main_sha` field without migration.

#### Scenario: Old cache still works
- **GIVEN** a pre-upgrade `e2e-baseline.json` with a valid `main_sha` matching the current HEAD
- **WHEN** `_get_or_create_e2e_baseline` runs after the upgrade
- **THEN** it returns the cached result without regenerating
- **AND** no `.lock` file needs to exist for the happy-path cache hit (the lock is only acquired when regeneration is required)
## Requirements

### Requirement: E2E gate retry_context preserves error-tail evidence

The web module's E2E gate (`execute_e2e_gate` in `modules/web/set_project_web/gates.py`) SHALL construct `retry_context` such that Playwright assertion errors, stack traces, and failure reason messages — which conventionally appear near the end of stdout — are preserved when the output exceeds the budget.

The gate SHALL NOT use a head-only slice (e.g., `e2e_output[:N]`) to truncate the output embedded in retry_context. It SHALL use `smart_truncate_structured` from `lib/set_orch/truncate.py` (or an equivalent utility providing head + tail preservation with error-line extraction from the middle).

The truncation budget SHALL be at least 6000 characters for the E2E output section of retry_context, chosen so that after the failing-test header (up to ~1500 chars for large failure sets) there remains a meaningful head and tail from the raw Playwright output. The budget MAY be smaller in proportion to the actual output length when the output is small.

#### Scenario: Playwright output with assertion errors at the tail

- **GIVEN** `e2e_output` is 32000 chars long and contains prisma setup noise in the first 10 000 chars, the per-test registration list in the middle, and Playwright assertion error messages with stack traces in the last 5 000 chars
- **AND** two tests fail with distinct assertion error messages
- **WHEN** `execute_e2e_gate` builds `retry_context`
- **THEN** the retry_context SHALL include text that contains at least one of the assertion error messages OR error-marker lines (e.g., `Error:`, `expected`, `Timeout`, `FAIL`) preserved from the tail or middle
- **AND** the retry_context SHALL NOT end abruptly mid-sentence inside prisma generate output (e.g., not end with `"Running generate... ["`)
- **AND** the retry_context SHALL include the list of failing test files/lines (existing header behavior preserved)

#### Scenario: Output within budget is passed through unchanged

- **GIVEN** `e2e_output` is 3000 chars long and the truncation budget is 6000
- **WHEN** `execute_e2e_gate` builds `retry_context`
- **THEN** the full `e2e_output` SHALL appear in retry_context without a truncation marker

#### Scenario: Failing-test header is preserved regardless of truncation

- **GIVEN** 33 tests fail and the failing-test header consumes ~1500 chars
- **WHEN** `execute_e2e_gate` builds `retry_context`
- **THEN** the `"E2E: N NEW failures"` header and the full `"New failures: <comma-separated list>"` SHALL appear verbatim in retry_context before the truncated output section

### Requirement: Default web template enables the unit test gate

The `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` file — copied verbatim into newly initialized consumer projects by `set-project init` — SHALL ship with `test_command: pnpm test` uncommented (active). The template MAY include a comment line clarifying that the unit test gate is a no-op (skipped) when no test files are present in the consumer project.

This default applies only to newly initialized projects. Existing consumer projects are not automatically re-initialized and retain whatever `test_command` value they have.

#### Scenario: Fresh consumer project has active test_command

- **GIVEN** a developer runs `set-project init --project-type web --template nextjs` against a clean repository
- **WHEN** the generated `set/orchestration/config.yaml` is read
- **THEN** the file SHALL contain an active (uncommented) `test_command:` entry with a value of `pnpm test`

#### Scenario: Unit test gate is a no-op when no tests exist

- **GIVEN** the consumer project's `package.json` has a `"test"` script that exits non-zero with "no tests found" (or similar) when no test files exist
- **AND** `test_command` is set to `pnpm test`
- **WHEN** a change is run and no vitest/jest files exist in the worktree
- **THEN** the test gate SHALL classify the outcome as `skipped` rather than `fail` — per the existing test-gate skipped-on-no-tests handling
- **AND** the gate SHALL NOT block the verify pipeline
