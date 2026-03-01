## Requirements

### Requirement: Verify gate step order (DELTA)
The verify gate step order SHALL be updated to include smoke testing.

#### Scenario: Full gate pipeline with smoke
- **WHEN** a change completes (Ralph done)
- **THEN** the verify gate SHALL execute in this order:
  1. **Test execution** — run `test_command` if configured
  2. **Build verification** — run `build` or `build:ci` from package.json
  3. **Test file existence check** — warning only
  4. **Smoke test** — run `smoke_command` if configured (NEW)
  5. **LLM code review** — if `review_before_merge: true`
  6. **OpenSpec verify** — run `/opsx:verify {change_name}`

#### Scenario: Smoke failure skips review and verify
- **WHEN** smoke tests fail
- **THEN** the gate SHALL NOT proceed to LLM review or OpenSpec verify
- **AND** SHALL retry the agent with smoke failure context

### Requirement: Smoke gate state tracking (DELTA)
The verify gate SHALL track smoke test state fields.

#### Scenario: State fields after smoke verification
- **WHEN** a change passes through the smoke gate step
- **THEN** the change state SHALL include: `smoke_result` (pass/fail/skip), `smoke_output` (truncated to 2000 chars), `gate_smoke_ms`
- **AND** `gate_total_ms` SHALL include `gate_smoke_ms` in its sum
