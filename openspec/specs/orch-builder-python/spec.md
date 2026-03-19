## ADDED Requirements

### Requirement: Python base build check
The system SHALL provide `check_base_build()` in `lib/set_orch/builder.py` that detects the project's package manager (npm/pnpm/yarn/bun), runs the build script, and caches the result for the session.

#### Scenario: Build succeeds
- **WHEN** the project has a build script and it exits 0
- **THEN** the result is cached as "pass" and the function returns success

#### Scenario: Build fails
- **WHEN** the build script exits non-zero
- **THEN** the result is cached as "fail" and LLM-assisted fix is attempted

#### Scenario: No build script
- **WHEN** no build script is found in package.json
- **THEN** the check is skipped and returns success

#### Scenario: Cached result reuse
- **WHEN** a build check was already performed in this session
- **THEN** the cached result is returned without re-running the build

### Requirement: Python LLM-assisted build fix
The system SHALL provide `fix_base_build_with_llm()` in `builder.py` that attempts to fix build errors using Claude with model escalation (sonnet first, then opus if sonnet fails).

#### Scenario: Sonnet fixes the build
- **WHEN** the build fails and sonnet is invoked with the error output
- **THEN** sonnet's fix is applied and the build is re-run successfully

#### Scenario: Sonnet fails, opus escalation
- **WHEN** sonnet's fix does not resolve the build error
- **THEN** opus is invoked with the same error context for a second attempt

#### Scenario: Non-blocking on total failure
- **WHEN** both sonnet and opus fail to fix the build
- **THEN** the function logs the failure and returns 0 (non-blocking)

### Requirement: Bash builder.sh becomes thin wrapper
After migration, `builder.sh` SHALL contain only delegation to `set-orch-core build check`.

#### Scenario: Thin wrapper delegation
- **WHEN** `check_base_build()` is called in bash
- **THEN** it delegates to `set-orch-core build check` with equivalent arguments
