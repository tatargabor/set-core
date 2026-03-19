## MODIFIED Requirements

### Requirement: Post-init health summary
After deploying hooks, commands, and skills, `set-project init` SHALL run `wt-audit scan` and display a summary of project health.

#### Scenario: Init with gaps
- **WHEN** `set-project init` completes and audit finds ❌ or ⚠️ items
- **THEN** output shows the summary line (e.g., `Health: ✅ 10  ⚠️ 3  ❌ 2`) and suggests running `/wt:audit` to address gaps

#### Scenario: Init with clean health
- **WHEN** `set-project init` completes and audit finds all ✅
- **THEN** output shows `Health: ✅ all checks passed`

#### Scenario: Audit not available
- **WHEN** `wt-audit` is not in PATH (e.g., partial install)
- **THEN** `set-project init` skips the audit step without error
