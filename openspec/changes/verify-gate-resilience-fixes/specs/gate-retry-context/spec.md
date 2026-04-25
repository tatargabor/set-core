## ADDED Requirements

### Requirement: Scoped-subset spec-existence pre-validation
Before the e2e gate enters scoped-subset mode, the gate runner SHALL filter the candidate spec list (from `retry_diff_files`) against `Path.exists()`. If 0 valid paths remain after filtering, the gate SHALL bypass subset mode entirely and fall through to the existing fallback (own-specs / full).

#### Scenario: All bogus paths trigger fallback
- **WHEN** `retry_diff_files` returns paths to spec files that do not exist in the worktree
- **THEN** the gate runner does NOT spawn a subprocess to run the empty subset
- **AND** does NOT log a misleading `Scoped gate: e2e running on N items` message
- **AND** falls through to fallback mode directly
