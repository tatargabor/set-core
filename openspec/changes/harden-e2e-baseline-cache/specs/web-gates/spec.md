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
