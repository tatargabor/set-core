## IN SCOPE
- Profile hook interface: pre_dispatch_checks and post_verify_hooks methods
- Hook composition: directive hooks + profile hooks at each lifecycle point
- NullProfile default implementations (no-op)

## OUT OF SCOPE
- Async hook execution
- Hook priority/ordering customization
- Concrete web profile hook implementations (belongs in set-project-web)
- User-facing hook configuration UI

### Requirement: Profile shall support pre-dispatch checks
The profile interface SHALL define `pre_dispatch_checks(change_type: str, wt_path: str) -> list[str]` returning a list of error messages. An empty list means all checks pass. Non-empty list blocks dispatch.

#### Scenario: Pre-dispatch check passes
- **GIVEN** profile.pre_dispatch_checks() returns empty list
- **WHEN** dispatch_change() runs pre-dispatch validation
- **THEN** dispatch SHALL proceed normally

#### Scenario: Pre-dispatch check fails
- **GIVEN** profile.pre_dispatch_checks() returns ["Playwright not found"]
- **WHEN** dispatch_change() runs pre-dispatch validation
- **THEN** dispatch SHALL NOT start the Ralph loop
- **AND** SHALL log the error messages
- **AND** SHALL mark the change status appropriately

#### Scenario: NullProfile pre-dispatch always passes
- **WHEN** NullProfile().pre_dispatch_checks("feature", "/any/path") is called
- **THEN** it SHALL return an empty list

### Requirement: Profile shall support post-verify hooks
The profile interface SHALL define `post_verify_hooks(change_name: str, wt_path: str, gate_results: list) -> None`. This runs after the gate pipeline returns "continue" (all gates passed), before adding to merge queue. Exceptions SHALL be caught and logged without blocking merge.

#### Scenario: Post-verify hook runs on success
- **GIVEN** gate pipeline returns "continue"
- **WHEN** handle_change_done processes the result
- **THEN** profile.post_verify_hooks() SHALL be called with change_name, wt_path, and gate results

#### Scenario: Post-verify hook exception does not block
- **GIVEN** profile.post_verify_hooks() raises an exception
- **WHEN** handle_change_done catches it
- **THEN** the exception SHALL be logged at warning level
- **AND** the change SHALL still be added to merge queue

#### Scenario: NullProfile post-verify is no-op
- **WHEN** NullProfile().post_verify_hooks("any", "/any", []) is called
- **THEN** it SHALL return without side effects

### Requirement: Hook composition shall combine directive and profile hooks
At each lifecycle point (pre-dispatch, post-verify), the engine SHALL run directive hooks (shell scripts from orchestration.yaml) first, then profile hooks (Python methods). Both run independently.

#### Scenario: Directive hook fails, profile hook still runs pre-dispatch
- **GIVEN** hook_pre_dispatch shell script exits non-zero
- **WHEN** dispatch_change() processes hooks
- **THEN** dispatch SHALL be blocked (existing behavior)
- **AND** profile.pre_dispatch_checks() SHALL NOT run (dispatch already blocked)

#### Scenario: Both directive and profile hooks run post-verify
- **GIVEN** hook_post_verify shell script is configured
- **AND** profile has post_verify_hooks implementation
- **WHEN** gate pipeline returns "continue"
- **THEN** directive hook SHALL run first
- **AND** profile hook SHALL run second
