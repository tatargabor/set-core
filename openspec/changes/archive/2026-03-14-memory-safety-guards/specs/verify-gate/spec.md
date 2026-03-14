## MODIFIED Requirements

### Requirement: Verify skill memory safety rule
The verify skill (`openspec-verify-change/SKILL.md`) SHALL include an explicit rule that prevents memory from substituting filesystem verification.

#### Scenario: Agent receives memory suggesting false positive
- **WHEN** the verify skill runs and memory context suggests "this is a known false positive" or "same pattern as before"
- **THEN** the agent SHALL still perform filesystem checks (Glob, Grep, Read) for every requirement
- **AND** the agent SHALL NOT conclude PASS based on memory alone

#### Scenario: Memory suggests implementation exists but files are absent
- **WHEN** memory states implementation was previously verified as present
- **AND** the current filesystem does not contain the expected files
- **THEN** the agent SHALL report CRITICAL issues for missing files
- **AND** the agent SHALL note that memory context does not match current filesystem state

#### Scenario: Memory suggests issues but files exist and are correct
- **WHEN** memory states implementation has issues
- **AND** the current filesystem shows files exist and satisfy requirements
- **THEN** the agent SHALL report PASS based on filesystem evidence

### Requirement: Verifier safety prompt injection
The orchestrator's verify gate (`verifier.sh`) SHALL inject a memory-safety instruction into the verify prompt before invoking Claude.

#### Scenario: Automated verify call includes safety prompt
- **WHEN** the orchestrator runs `/opsx:verify` for a change via `run_claude`
- **THEN** the prompt SHALL include an instruction that memory cannot replace filesystem checks
- **AND** the prompt SHALL note that memory is not branch/worktree-aware

### Requirement: Verify outcome memory feedback
The orchestrator SHALL save feedback memories based on verify gate outcomes.

#### Scenario: Verify passes — promotion memory
- **WHEN** the verify gate produces `VERIFY_RESULT: PASS`
- **THEN** the orchestrator SHALL save a memory via `orch_remember()` with tags `phase:verified,change:<name>` confirming the implementation was verified on the filesystem

#### Scenario: Verify fails — quarantine memory
- **WHEN** the verify gate produces `VERIFY_RESULT: FAIL` or the heuristic detects critical issues
- **THEN** the orchestrator SHALL save a memory via `orch_remember()` with tags `phase:verify-failed,change:<name>,volatile` warning that previous memories about this change may be inaccurate

#### Scenario: Quarantine memory decays
- **WHEN** a quarantine memory was created more than 24 hours ago
- **THEN** it SHALL be filtered out by `orch_recall()` via the volatile decay mechanism

### Requirement: CLAUDE.md memory safety section
The CLAUDE.md template SHALL include a brief "Memory Safety During Verification" section under the Persistent Memory documentation.

#### Scenario: Agent reads CLAUDE.md during verify
- **WHEN** an agent session starts and CLAUDE.md is loaded
- **THEN** the agent SHALL see a rule that memory is a hypothesis, not a verdict, during verification
