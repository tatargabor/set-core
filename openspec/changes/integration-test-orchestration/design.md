# Design: Integration Test Orchestration

## Context

The Python orchestration pipeline (merger.py, verifier.py, state.py) lacks integration tests that exercise real git operations. The existing bash integration test targets the legacy bash layer. E2E runs are the only validation but are expensive ($30-80) and slow (1-3h). A middle layer is needed: real git, real Python code, stubbed external CLIs.

## Goals / Non-Goals

**Goals:**
- Test the top 10 recurring bug patterns from E2E runs with deterministic, fast tests
- Use real git repos (init, commit, branch, merge, worktree) — not mocked
- Stub only external CLIs (set-merge, openspec, set-close) that would require LLM or complex setup
- Run in <30 seconds in CI alongside existing test suite

**Non-Goals:**
- Test LLM conflict resolution quality (that's Layer 2 / E2E gauntlet)
- Test sentinel process management or bash orchestrator
- Achieve 100% code coverage of merger/verifier — focus on bug regression

## Decisions

### 1. Stub strategy: PATH override with shell scripts
**Decision:** Create minimal bash scripts in `tests/integration/fixtures/bin/` and prepend to PATH via pytest fixture.

**Rationale:** The merger.py calls `set-merge`, `openspec`, `set-close` via `run_command()` which uses `subprocess.run()`. PATH override is the simplest, most realistic stub — the Python code runs exactly as in production, only the external CLIs are swapped.

**Alternatives considered:**
- `@patch("set_orch.merger.run_command")` — too fragile, need different responses for dozens of git vs CLI calls
- Dependency injection — would require refactoring production code

**Stub behaviors:**
- `set-merge <name> --no-push --llm-resolve`: runs `git merge change/<name> --no-edit`, exit 0 on success, exit 1 on conflict
- `openspec archive <name> --yes`: no-op, exit 0
- `set-close <name>`: no-op, exit 0 (worktree cleanup tested separately)

### 2. Test organization: one file per subsystem
**Decision:** Three test files: `test_merge_pipeline.py`, `test_verify_gates.py`, `test_state_machine.py`

**Rationale:** Maps to the three Python modules being tested (merger.py, verifier.py, state.py). Each file can run independently.

### 3. Fixture design: factory functions, not class hierarchies
**Decision:** Use pytest fixtures that return factory functions for creating repos, branches, and state files.

**Rationale:** Each test needs slightly different repo setups. Factories allow composability without complex inheritance. `tmp_path` ensures cleanup.

### 4. Selective function testing vs full pipeline
**Decision:** Test both individual functions (e.g., `git_has_uncommitted_work()`, `_try_merge()`) AND composite flows (e.g., `execute_merge_queue()` with 3 changes).

**Rationale:** Individual function tests catch specific regressions. Composite tests validate the integration between functions — which is where most E2E bugs originated.

## Risks / Trade-offs

- **[Risk] set-merge stub doesn't match real behavior** → Mitigation: stub does real `git merge`, just without LLM conflict resolution. Conflict scenarios tested explicitly.
- **[Risk] merger.py has side effects (hooks, events, coverage updates)** → Mitigation: stub/patch hook and event systems. Focus tests on git state and orchestration state changes.
- **[Risk] Tests become brittle if internal APIs change** → Mitigation: test public functions (merge_change, execute_merge_queue, handle_change_done) not private helpers.

## Open Questions

- Should we also test `retry_merge_queue()` or is `execute_merge_queue()` sufficient? (Answer: test both — retry is where fingerprint dedup lives)
- How much of the verify gate pipeline should we stub? (Answer: stub individual gates as pass/fail, test the pipeline runner logic)
