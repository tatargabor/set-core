# Tasks: Fix engine.sh arithmetic crash (ISS-001)

## 1. Fix pipefail-safe grep pipeline

- [x] 1.1 Wrap grep command in `{ grep ... || true; }` so pipefail doesn't leak multi-line output [REQ: pipefail-safe-grep-pipeline]
- [x] 1.2 Add `reminder_chars=${reminder_chars:-0}` default guard after grep pipeline [REQ: pipefail-safe-grep-pipeline]

## 2. Fix pipefail-safe sed pipeline

- [x] 2.1 Wrap sed command in `{ sed ... || true; }` so pipefail doesn't leak multi-line output [REQ: pipefail-safe-sed-pipeline]
- [x] 2.2 Add `reminder_chars=${reminder_chars:-0}` default guard after sed pipeline [REQ: pipefail-safe-sed-pipeline]

## 3. Fix trap-safe cleanup variable

- [x] 3.1 Use `${cleanup_done:-false}` guard in cleanup_on_exit trap handler [REQ: trap-safe-cleanup-variable]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN iter log has no system-reminder blocks THEN reminder_chars is `0` and arithmetic succeeds [REQ: pipefail-safe-grep-pipeline, scenario: grep-finds-no-system-reminder-blocks]
- [x] AC-2: WHEN iter log has system-reminder blocks THEN reminder_chars is correct byte count [REQ: pipefail-safe-grep-pipeline, scenario: grep-finds-matching-blocks]
- [x] AC-3: WHEN iter log has no multiline reminders THEN sed pipeline sets reminder_chars to `0` [REQ: pipefail-safe-sed-pipeline, scenario: sed-finds-no-multiline-reminders]
- [x] AC-4: WHEN trap fires before cleanup_done is assigned THEN guard evaluates to false and cleanup proceeds [REQ: trap-safe-cleanup-variable, scenario: trap-fires-before-variable-initialization]
