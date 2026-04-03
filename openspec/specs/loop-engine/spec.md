# Spec: loop-engine

## Requirements

### Requirement: Memory injection estimation

The loop engine SHALL estimate memory injection size by scanning iteration logs for `<system-reminder>` blocks. The estimation code SHALL be resilient to shell option combinations (`pipefail`, `nounset`, `errexit`) and SHALL NOT crash when no reminder blocks are found in the log.

#### Scenario: No system-reminder blocks in iteration log
- **WHEN** the iteration log contains no `<system-reminder>` blocks
- **THEN** `reminder_chars` is set to 0 and context breakdown completes without error

#### Scenario: Cleanup trap fires before initialization
- **WHEN** the cleanup trap fires before `cleanup_done` has been assigned
- **THEN** the trap handler completes without an unbound variable error
