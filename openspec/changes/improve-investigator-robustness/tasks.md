## 1. Policy config plumbing

- [x] 1.1 Add `max_turns: int = 40` to `InvestigationConfig` in `lib/set_orch/issues/policy.py` [REQ: investigator-max-turns-is-configurable-via-policy] [REQ: config-schema-includes-investigation-max-turns]
- [x] 1.2 Add `diagnosed_stall_hours: int = 2` as a top-level field on `IssuesPolicyConfig` [REQ: config-schema-includes-diagnosed-stall-hours]
- [x] 1.3 Update `IssuesPolicyConfig.from_dict` to read `investigation.max_turns` (default 40) and `diagnosed_stall_hours` (default 2), preserving other keys' behavior [REQ: config-schema-includes-investigation-max-turns] [REQ: config-schema-includes-diagnosed-stall-hours]
- [x] 1.4 Update `IssuesPolicyConfig.from_dict` to read `auto_fix_conditions.low_confidence_after_hours` if present; store it in the resulting `auto_fix_conditions` dict [REQ: auto_fix_conditions-supports-low_confidence_after_hours]
- [x] 1.5 Add unit tests in `tests/unit/test_issue_policy_config.py` covering: default values, YAML load of each new field, absent-key fallback [REQ: config-schema-includes-investigation-max-turns] [REQ: config-schema-includes-diagnosed-stall-hours] [REQ: auto_fix_conditions-supports-low_confidence_after_hours]

## 2. Investigator uses configurable max_turns

- [x] 2.1 In `lib/set_orch/issues/investigator.py:spawn`, replace the hardcoded `"--max-turns", "20"` with `"--max-turns", str(self.config.investigation.max_turns)` [REQ: investigator-max-turns-is-configurable-via-policy]
- [x] 2.2 Add unit test in `tests/unit/test_investigator_max_turns.py` that stubs `subprocess.Popen` and verifies the command line contains `--max-turns 40` with default config, and `--max-turns 60` when the config override is applied [REQ: investigator-max-turns-is-configurable-via-policy]

## 3. Investigator prompt — source corruption hint

- [x] 3.1 Append a "Source corruption recognition" section to `INVESTIGATION_PROMPT` in `lib/set_orch/issues/investigator.py` covering: duplicate imports, repeated code blocks, leftover merge markers, and the instruction to emit a partial-diagnosis exit with the recommended `git diff HEAD~1 -- <file>` step [REQ: investigator-prompt-recognises-source-corruption]
- [x] 3.2 Add a unit test in `tests/unit/test_investigator_prompt.py` that formats the prompt and asserts the corruption section is present, the `git diff HEAD~1` recommendation is present, and the "partial diagnosis is acceptable" language is present [REQ: investigator-prompt-recognises-source-corruption]

## 4. DIAGNOSED-stall watchdog

- [x] 4.1 Add `_check_diagnosed_stalls()` method on `IssueManager` in `lib/set_orch/issues/manager.py` that iterates issues in DIAGNOSED state, compares `diagnosed_at` to `diagnosed_stall_hours` threshold, and records one-time notification + audit entry [REQ: diagnosed-watchdog-notifies-once-on-stall]
- [x] 4.2 Skip issues already marked `issue.extras["stalled_notification_sent"] == True` [REQ: diagnosed-watchdog-notifies-once-on-stall]
- [x] 4.3 On threshold-cross: audit-log `diagnosis_stalled_notification_sent` with elapsed-seconds field; call `getattr(self.notifier, 'on_stalled_diagnosis', None)` and invoke if callable; set `issue.extras["stalled_notification_sent"] = True` [REQ: diagnosed-watchdog-notifies-once-on-stall]
- [x] 4.4 Wrap the whole check in try/except at the call site so a watchdog crash does not break `tick()`; log WARN on exception [REQ: tick-loop-includes-diagnosed-stall-watchdog]
- [x] 4.5 Invoke `_check_diagnosed_stalls()` from `tick()` after the `_process(issue)` loop and before `_check_timeout_reminders` [REQ: tick-loop-includes-diagnosed-stall-watchdog]
- [x] 4.6 Add unit tests in `tests/unit/test_diagnosed_stall_watchdog.py` covering: under-threshold no-op, threshold-crossed fires notification + audit + extras flag, second tick does not re-fire, no-notifier still audits, notifier without `on_stalled_diagnosis` still audits, exception path isolated from tick [REQ: diagnosed-watchdog-notifies-once-on-stall] [REQ: tick-loop-includes-diagnosed-stall-watchdog]

## 5. Low-confidence auto-fix escape (opt-in)

- [x] 5.1 In `PolicyEngine` (or the equivalent `_apply_post_diagnosis_policy` routing function), after the existing min_confidence check, add a secondary branch: if the escape key is set AND elapsed-hours > N AND confidence >= 0.4, promote to FIXING and audit-log `low_confidence_auto_fix_approved` [REQ: low-confidence-auto-fix-escape-opt-in]
- [x] 5.2 Default-disabled behavior: when the escape key is absent or None, the branch never fires [REQ: low-confidence-auto-fix-escape-opt-in]
- [x] 5.3 Add unit tests in `tests/unit/test_low_confidence_escape.py` covering: disabled (absent), enabled but confidence too low, enabled but elapsed too short, all conditions met → promoted [REQ: low-confidence-auto-fix-escape-opt-in]

## 6. Recovery preview — active-issue warning

- [x] 6.1 In `lib/set_orch/recovery.py:render_preview`, after the existing sections, add logic that reads the issues registry at `project_path/.set/issues/registry.json` [REQ: rollback-preview-warns-about-active-issues-outside-rollback-scope]
- [x] 6.2 Filter issues to those with state in {INVESTIGATING, DIAGNOSED, AWAITING_APPROVAL, FIXING} AND whose `affected_change` is NOT in `plan.rollback_changes` [REQ: rollback-preview-warns-about-active-issues-outside-rollback-scope]
- [x] 6.3 If the filtered list is non-empty, append a "  ⚠ Active fix-iss pipelines outside rollback scope:" section with one line per issue: id, state, affected_change, child name [REQ: rollback-preview-warns-about-active-issues-outside-rollback-scope]
- [x] 6.4 Gracefully handle registry-missing / malformed-JSON: skip the section, log DEBUG, never raise [REQ: rollback-preview-warns-about-active-issues-outside-rollback-scope]
- [x] 6.5 Add unit tests in `tests/unit/test_recovery_preview_warnings.py` covering: no active issues → section omitted, active inside scope → not listed, active outside scope → listed, terminal issues excluded, registry-missing handled gracefully [REQ: rollback-preview-warns-about-active-issues-outside-rollback-scope]

## 7. Integration validation

- [x] 7.1 Run the full issue test suite (`pytest tests/unit/test_issue_state_machine.py tests/unit/test_issues_auto_resolve.py tests/unit/test_fix_iss_escalation.py tests/unit/test_issue_registry.py tests/unit/test_issues_watchdog.py`) and confirm no regressions beyond the known-pre-existing failures [REQ: tick-loop-includes-diagnosed-stall-watchdog]
- [x] 7.2 Manual smoke: set `diagnosed_stall_hours=0` in a tmp config, seed a DIAGNOSED issue, call `tick()`, verify notification fires once and not again on second tick [REQ: diagnosed-watchdog-notifies-once-on-stall]

## Acceptance Criteria (from spec scenarios)

### investigation-robustness

- [x] AC-1: Default-config `spawn` calls claude with `--max-turns 40` [REQ: investigator-max-turns-is-configurable-via-policy, scenario: default-max_turns-propagated]
- [x] AC-2: Override-config `spawn` calls claude with `--max-turns 60` [REQ: investigator-max-turns-is-configurable-via-policy, scenario: overridden-max_turns-propagated]
- [x] AC-3: `from_dict({"investigation": {"max_turns": 30}})` produces `investigation.max_turns == 30` [REQ: investigator-max-turns-is-configurable-via-policy, scenario: config-loading-reads-max_turns]
- [x] AC-4: `from_dict` with missing `max_turns` falls back to 40 [REQ: investigator-max-turns-is-configurable-via-policy, scenario: missing-key-falls-back-to-default]
- [x] AC-5: First stall crossing threshold emits `diagnosis_stalled_notification_sent` audit + notifier call + extras flag [REQ: diagnosed-watchdog-notifies-once-on-stall, scenario: first-stall-crosses-threshold-notify-once]
- [x] AC-6: Subsequent ticks for a flagged issue do not re-notify [REQ: diagnosed-watchdog-notifies-once-on-stall, scenario: subsequent-ticks-do-not-re-notify]
- [x] AC-7: Issues below threshold elapsed are no-op [REQ: diagnosed-watchdog-notifies-once-on-stall, scenario: fresh-diagnosed-below-threshold-no-op]
- [x] AC-8: No-notifier case still audits [REQ: diagnosed-watchdog-notifies-once-on-stall, scenario: no-notifier-attached-audit-only]
- [x] AC-9: Notifier without `on_stalled_diagnosis` method still audits [REQ: diagnosed-watchdog-notifies-once-on-stall, scenario: notifier-missing-on_stalled_diagnosis-audit-only]
- [x] AC-10: Escape disabled (None / 0) never promotes low-confidence [REQ: low-confidence-auto-fix-escape-opt-in, scenario: escape-disabled-by-default]
- [x] AC-11: Escape fires with all conditions met → FIXING transition [REQ: low-confidence-auto-fix-escape-opt-in, scenario: escape-fires-promote-to-fixing]
- [x] AC-12: Escape rejects confidence < 0.4 [REQ: low-confidence-auto-fix-escape-opt-in, scenario: escape-rejects-too-low-confidence]
- [x] AC-13: Prompt includes corruption section [REQ: investigator-prompt-recognises-source-corruption, scenario: corruption-section-present-in-prompt]
- [x] AC-14: Prompt names the recommended diagnosis + `git diff HEAD~1` step + partial-diagnosis permission [REQ: investigator-prompt-recognises-source-corruption, scenario: exit-advice-is-specific]

### issue-state-machine

- [x] AC-15: `tick()` calls `_check_diagnosed_stalls()` at least once per invocation after the process loop [REQ: tick-loop-includes-diagnosed-stall-watchdog, scenario: tick-sequence-includes-the-watchdog]
- [x] AC-16: Watchdog exception is caught; `_check_timeout_reminders` still runs [REQ: tick-loop-includes-diagnosed-stall-watchdog, scenario: watchdog-errors-do-not-break-tick]

### issue-policy-engine

- [x] AC-17: `InvestigationConfig().max_turns == 40` [REQ: config-schema-includes-investigation-max-turns, scenario: default-value]
- [x] AC-18: YAML-loaded `max_turns=30` materializes correctly [REQ: config-schema-includes-investigation-max-turns, scenario: field-is-loaded-from-yaml-via-from_dict]
- [x] AC-19: `IssuesPolicyConfig().diagnosed_stall_hours == 2` [REQ: config-schema-includes-diagnosed-stall-hours, scenario: default-value]
- [x] AC-20: YAML-loaded `diagnosed_stall_hours=1` materializes [REQ: config-schema-includes-diagnosed-stall-hours, scenario: field-is-loaded-from-yaml-via-from_dict]
- [x] AC-21: Default `auto_fix_conditions` does not include a non-None `low_confidence_after_hours` [REQ: auto_fix_conditions-supports-low_confidence_after_hours, scenario: default-omits-the-escape]
- [x] AC-22: `from_dict` with the escape key stores it [REQ: auto_fix_conditions-supports-low_confidence_after_hours, scenario: explicit-opt-in]

### dispatch-recovery

- [x] AC-23: Active issue inside rollback scope → not listed [REQ: rollback-preview-warns-about-active-issues-outside-rollback-scope, scenario: active-issue-inside-rollback-scope-not-listed]
- [x] AC-24: Active issue outside rollback scope → listed with id / state / affected / child [REQ: rollback-preview-warns-about-active-issues-outside-rollback-scope, scenario: active-issue-outside-rollback-scope-listed]
- [x] AC-25: No outside-scope active issues → section omitted [REQ: rollback-preview-warns-about-active-issues-outside-rollback-scope, scenario: no-active-outside-scope-issues-section-omitted]
- [x] AC-26: Terminal-state issues never listed [REQ: rollback-preview-warns-about-active-issues-outside-rollback-scope, scenario: terminal-state-issues-ignored]
- [x] AC-27: Registry missing / malformed — graceful, no raise [REQ: rollback-preview-warns-about-active-issues-outside-rollback-scope, scenario: registry-unreadable-graceful-degradation]
