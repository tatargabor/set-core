## ADDED Requirements

## IN SCOPE
- Dispatcher reads `ikp_packs` from change metadata and injects L3 rules into worktree
- Dispatcher adds IKP summary section to input.md
- IKP rule files in `.claude/rules/ikp-<pack>.md`

## OUT OF SCOPE
- IKP pack loading internals (handled by ikp-bridge)
- L5 Operations injection
- IKP-specific gate overrides

### Requirement: Dispatcher injects IKP rules into worktree
The dispatcher SHALL read `ikp_packs` from the change metadata and call `ikp_bridge.inject_rules_for_change()` to write L3 implementation layers as rule files into the worktree's `.claude/rules/` directory.

#### Scenario: Change with IKP packs
- **WHEN** dispatching a change with `ikp_packs: ["billingo"]`
- **AND** `has_ikp_pipeline()` returns True
- **THEN** the dispatcher SHALL create `<wt>/.claude/rules/ikp-billingo.md`
- **AND** the file SHALL contain auth patterns, error handling code, and API boilerplate for TypeScript

#### Scenario: Change with multiple packs
- **WHEN** dispatching a change with `ikp_packs: ["billingo", "wise-payments"]`
- **THEN** the dispatcher SHALL create both `ikp-billingo.md` and `ikp-wise-payments.md`

#### Scenario: Change without IKP packs
- **WHEN** dispatching a change with empty or missing `ikp_packs`
- **THEN** the dispatcher SHALL skip IKP rule injection entirely

#### Scenario: IKP pipeline disabled
- **WHEN** `has_ikp_pipeline()` returns False
- **THEN** the dispatcher SHALL skip IKP rule injection regardless of `ikp_packs` value

#### Scenario: Injection timing
- **WHEN** the dispatcher runs the dispatch sequence
- **THEN** IKP rule injection SHALL occur after design source deployment and before input.md assembly

### Requirement: IKP summary in input.md
The dispatcher SHALL add a brief IKP summary section to the agent's input.md when the change has IKP packs. The section SHALL contain pack capabilities, required env vars, and key pitfalls.

#### Scenario: IKP section content
- **WHEN** the change has `ikp_packs: ["billingo"]`
- **THEN** input.md SHALL contain a `## Integration Packs (IKP)` section
- **AND** the section SHALL list capabilities with complexity ratings
- **AND** the section SHALL list required environment variables
- **AND** the section SHALL list key pitfalls
- **AND** the section SHALL reference `.claude/rules/ikp-*.md` for full implementation patterns

#### Scenario: Token budget for IKP summary
- **WHEN** the IKP summary is built
- **THEN** each pack summary SHALL be limited to ~200 tokens (metadata only, not full L3 content)
