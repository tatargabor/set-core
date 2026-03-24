# Tasks

## 1. Merge queue always receives done changes (verifier.py)

- [x] 1.1 In `handle_change_done()`, remove the `if merge_policy in ("eager", "checkpoint")` guard — always add to merge queue [REQ: merge-queue-always-receives-done-changes]
- [x] 1.2 Remove `merge_policy` parameter from `handle_change_done()` signature if no longer used elsewhere in the function [REQ: merge-queue-always-receives-done-changes] (kept param with default for backwards compat — no longer used in body)

## 2. Config defaults and validation (engine.py + config.py)

- [x] 2.1 Verify `Directives.merge_policy` default is "eager" in engine.py (already is — just confirm) [REQ: default-merge-policy-is-eager]
- [x] 2.2 In `config.py`, change merge_policy enum from `^(eager|checkpoint|manual)$` to `^(eager|checkpoint)$` [REQ: default-merge-policy-is-eager]

## 3. Template cleanup (modules/web + runners)

- [x] 3.1 In `modules/web/.../templates/nextjs/wt/orchestration/config.yaml`, remove `merge_policy`, `checkpoint_auto_approve`, and `checkpoint_every` lines [REQ: template-config-omits-checkpoint-settings]
- [x] 3.2 In `tests/e2e/runners/run-craftbrew.sh`, remove `merge_policy: checkpoint` and `checkpoint_auto_approve: true` from config generation [REQ: template-config-omits-checkpoint-settings]
- [x] 3.3 In `tests/e2e/runners/run-minishop.sh`, same cleanup if present [REQ: template-config-omits-checkpoint-settings]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a change completes verify gates THEN it is added to merge queue without checking merge_policy [REQ: merge-queue-always-receives-done-changes, scenario: done-change-auto-queued-regardless-of-config]
- [x] AC-2: WHEN config does not specify merge_policy THEN orchestrator uses "eager" [REQ: default-merge-policy-is-eager, scenario: no-merge-policy-in-config-uses-eager]
- [x] AC-3: WHEN set-project init creates a new project THEN config.yaml does not contain checkpoint keys [REQ: template-config-omits-checkpoint-settings, scenario: fresh-project-has-no-checkpoint-config]
