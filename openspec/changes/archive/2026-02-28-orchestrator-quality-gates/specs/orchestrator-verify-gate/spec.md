## MODIFIED Requirements

### Requirement: Verify gate checks
The verify gate SHALL execute the following steps in order before allowing merge:
1. Run tests (if `test_command` configured) — blocking
2. LLM code review (if `review_before_merge: true`) — blocking on CRITICAL
3. OpenSpec verify (`/opsx:verify`) — blocking
3b. Test file existence check — WARNING only
4. Build verification — blocking with retry

#### Scenario: Change with no test files
- **WHEN** a change completes and `git diff --name-only` contains zero files matching `*.test.*` or `*.spec.*`
- **THEN** a warning notification is sent: "Change 'X' has no test files"
- **AND** `has_tests` is set to `false` in state
- **AND** the gate does NOT block — merge proceeds

#### Scenario: Change with test files
- **WHEN** a change diff contains files matching `*.test.*` or `*.spec.*`
- **THEN** `has_tests` is set to `true` in state
- **AND** no warning is emitted

#### Scenario: Gate total includes build timing
- **WHEN** the verify gate completes all steps
- **THEN** `gate_total_ms` includes test + review + verify + build durations
- **AND** the log line includes `build=Nms`
