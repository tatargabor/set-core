## verify-gate

Test runner, scope checks, verification rule evaluation, and gate pipeline orchestration.

### Requirements

#### VG-RUN — Run tests in worktree
- Execute test command in worktree directory with configurable timeout
- Capture exit code and output, truncate to max_chars (default 2000)
- Return `TestResult` dataclass with passed, output, exit_code, stats
- Parse test counts from Jest/Vitest/Playwright output formats

#### VG-SCOPE-MERGE — Post-merge scope verification
- Diff HEAD~1 to find files changed in merge commit
- Filter out artifact/config/bootstrap paths (openspec/*, .claude/*, orchestration*, .wt-tools/*, prisma/dev.db, *.lock, jest.config.*, .gitignore, .env*)
- Return pass if any implementation file exists, fail if only artifacts

#### VG-SCOPE-IMPL — Pre-merge implementation scope check
- Diff worktree branch vs merge-base
- Same filter logic as VG-SCOPE-MERGE
- Return `ScopeCheckResult` with has_implementation, first_impl_file, all_files

#### VG-RULES — Verification rule evaluation
- Read verification_rules from project-knowledge.yaml
- For each rule: match trigger glob against changed files
- Error-severity rules return failure, warning-severity logged only
- Graceful degradation: no-op when yaml file missing or yq unavailable

#### VG-PIPELINE — Gate pipeline (handle_change_done)
- Ordered steps: build → test → e2e → scope check → test file check → review → rules → verify → merge queue
- Each step with retry logic (verify_retry_count vs max_verify_retries)
- Retry token tracking: snapshot tokens before retry, compute diff on return
- Merge-rebase fast path: skip verify gate for returning rebase changes
- Gate timing: accumulate per-step ms, emit VERIFY_GATE event with totals
- Per-change skip flags: skip_test, skip_review honored
- Build step: detect package manager, run build:ci or build script, check main branch on failure
- Test file existence check: blocking for feature/infrastructure/foundational types

#### VG-BUILD — Build verification
- Detect package.json build/build:ci scripts
- Detect package manager from lockfile
- On failure: check if main also broken, attempt fix_base_build_with_llm, sync and retry
- Store build_result and build_output in state
