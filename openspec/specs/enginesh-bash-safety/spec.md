# Spec: enginesh-bash-safety

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Preventing arithmetic errors from multi-line command substitution output in context tracking
- Preventing unbound variable crashes in trap handlers under `set -u`
- Ensuring `grep | wc -c` and `sed | wc -c` pipelines produce single-line numeric output under `pipefail`

### Out of scope
- Refactoring the context-tracking algorithm itself
- Changing the ralph loop iteration logic
- Modifying `set-common.sh` shell options

## Requirements

### Requirement: Pipefail-safe grep pipeline
The context-tracking `grep | wc -c` pipeline in engine.sh SHALL produce a single numeric value even when grep finds no matches under `set -euo pipefail`. The `|| true` fallback MUST be scoped inside `{ ... }` so its output doesn't append to the pipeline result.

#### Scenario: grep finds no system-reminder blocks
- **WHEN** the iter log file contains no `<system-reminder>` blocks
- **THEN** `reminder_chars` is set to `0` (single-line numeric), not `"0\n0"`
- **AND** the subsequent arithmetic expression `$(( reminder_chars / 4 ))` succeeds without error

#### Scenario: grep finds matching blocks
- **WHEN** the iter log file contains `<system-reminder>` blocks
- **THEN** `reminder_chars` is set to the correct byte count as a single numeric value

### Requirement: Pipefail-safe sed pipeline
The fallback `sed | wc -c` pipeline SHALL produce a single numeric value under the same conditions as the grep pipeline.

#### Scenario: sed finds no multiline reminders
- **WHEN** the iter log file contains no multiline `<system-reminder>` blocks
- **THEN** `reminder_chars` is set to `0` and arithmetic succeeds

### Requirement: Trap-safe cleanup variable
The `cleanup_done` variable referenced in the `cleanup_on_exit` trap handler SHALL use a default-value guard (`${cleanup_done:-false}`) so that `set -u` does not cause an unbound variable error if the trap fires before the variable is initialized.

#### Scenario: Trap fires before variable initialization
- **WHEN** the trap handler runs before `cleanup_done` is assigned
- **THEN** the guard evaluates to `false` and cleanup proceeds normally without crashing
