## ADDED Requirements

### Requirement: Build verification before merge
The verify gate SHALL detect the project's build command from `package.json` scripts (`build:ci` or `build`) and execute it before allowing merge.

#### Scenario: Build passes
- **WHEN** the worktree has `package.json` with a `build` script and the build succeeds
- **THEN** `build_result` is set to `"pass"` in state and the gate continues to merge

#### Scenario: Build fails with retries remaining
- **WHEN** the build fails and `verify_retry_count < max_verify_retries`
- **THEN** the agent is resumed with build error context (last 2000 chars of output)
- **AND** `verify_retry_count` is incremented

#### Scenario: Build fails permanently
- **WHEN** the build fails and all retries are exhausted
- **THEN** the change status is set to `"failed"`
- **AND** a critical notification is sent

#### Scenario: No build command detected
- **WHEN** the worktree has no `package.json` or no `build`/`build:ci` script
- **THEN** the build step is skipped entirely

### Requirement: Base build verification
When a worktree build fails, the orchestrator SHALL check if the main branch itself builds (`check_base_build()`). If main also fails, the orchestrator SHALL attempt an LLM-based fix (`fix_base_build_with_llm()`) and sync the worktree after the fix (`sync_worktree_with_main()`).

#### Scenario: Main branch build broken
- **WHEN** worktree build fails AND main branch build also fails
- **THEN** the orchestrator SHALL attempt LLM fix on main, commit the fix, and sync the worktree

#### Scenario: Main branch builds fine
- **WHEN** worktree build fails AND main branch build passes
- **THEN** the build failure is attributed to the change code and normal retry proceeds

### Requirement: Base build cache
The orchestrator SHALL cache the main branch build result in `BASE_BUILD_STATUS`/`BASE_BUILD_OUTPUT` variables. When a merge completes successfully, the cache SHALL be invalidated.

#### Scenario: Cache invalidation after merge
- **WHEN** a change is successfully merged to main
- **THEN** BASE_BUILD_STATUS and BASE_BUILD_OUTPUT SHALL be set to empty strings to force a fresh build check
