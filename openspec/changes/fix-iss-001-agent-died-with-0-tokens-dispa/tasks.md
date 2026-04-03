# Tasks: Fix bash arithmetic crash in engine.sh

## 1. Fix grep|wc pipeline crash

- [x] 1.1 Wrap grep in `{ grep ... || true; }` on line 592 to suppress no-match exit code [REQ: memory-injection-estimation]
- [x] 1.2 Wrap sed in `{ sed ... || true; }` on line 596 for consistency [REQ: memory-injection-estimation]
- [x] 1.3 Remove `|| echo 0` fallback pattern (source of double-output) [REQ: memory-injection-estimation]
- [x] 1.4 Add `${reminder_chars:-0}` default after each wc -c assignment [REQ: memory-injection-estimation]

## 2. Fix unbound variable in cleanup trap

- [x] 2.1 Change `$cleanup_done` to `${cleanup_done:-false}` in cleanup_on_exit guard [REQ: memory-injection-estimation]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN iteration log has no system-reminder blocks THEN reminder_chars is 0 and no crash [REQ: memory-injection-estimation, scenario: no-system-reminder-blocks-in-iteration-log]
- [x] AC-2: WHEN cleanup trap fires before cleanup_done is set THEN no unbound variable error [REQ: memory-injection-estimation, scenario: cleanup-trap-fires-before-initialization]
