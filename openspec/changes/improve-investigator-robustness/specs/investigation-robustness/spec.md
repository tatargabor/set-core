## IN SCOPE
- Configurable investigator `max_turns` budget plumbed from `IssuesPolicyConfig` to the claude CLI invocation.
- One-time watchdog notification for DIAGNOSED issues older than `diagnosed_stall_hours`.
- Opt-in low-confidence auto-fix escape hatch for long-stuck DIAGNOSED issues.
- Investigator prompt language that recognises source corruption (duplicate blocks / leftover merge markers) and exits with a usable diagnosis.

## OUT OF SCOPE
- Dispatcher-level pre-check for corrupt source files — the prompt hint is the first-pass fix; a pre-check is a future follow-up.
- Auto-retry of investigations that hit `max_turns`.
- Mid-investigation model escalation (sonnet → opus on cap).
- Changes to `_apply_post_diagnosis_policy` routing logic for fresh diagnoses.
- General rollback-impact analysis beyond active-issue enumeration.

## ADDED Requirements

### Requirement: Investigator max-turns is configurable via policy

`IssuesPolicyConfig.investigation.max_turns` SHALL control the `--max-turns` argument passed to the claude CLI when spawning an investigation. The default SHALL be 40 (up from the prior hardcoded 20). The value SHALL be propagated via `InvestigationRunner.spawn()` at each invocation.

#### Scenario: Default max_turns propagated
- **WHEN** `InvestigationRunner.spawn(issue)` is called with a default-config `IssuesPolicyConfig`
- **THEN** the spawned `claude` subprocess command line SHALL include `--max-turns 40`

#### Scenario: Overridden max_turns propagated
- **WHEN** `IssuesPolicyConfig.investigation.max_turns` is set to a different positive integer (e.g., 60)
- **THEN** the `claude` subprocess command line SHALL include `--max-turns 60` for that spawn

#### Scenario: Config loading reads max_turns
- **WHEN** `IssuesPolicyConfig.from_dict({"investigation": {"max_turns": 30}})` is called
- **THEN** the resulting config's `investigation.max_turns` SHALL equal 30

#### Scenario: Missing key falls back to default
- **WHEN** `from_dict` receives an `investigation` block without a `max_turns` key
- **THEN** `config.investigation.max_turns` SHALL equal the default (40)

### Requirement: DIAGNOSED watchdog notifies once on stall

The issue manager SHALL include a `_check_diagnosed_stalls()` step in its tick loop. For each DIAGNOSED issue whose `diagnosed_at` is older than `IssuesPolicyConfig.diagnosed_stall_hours` (default 2), the watchdog SHALL emit a one-time notification and audit entry. Repeat ticks SHALL NOT re-fire for the same issue.

#### Scenario: First stall crosses threshold — notify once
- **WHEN** an issue has been in DIAGNOSED for longer than `diagnosed_stall_hours`
- **AND** the watchdog has not already marked this issue as notified
- **THEN** an audit entry `diagnosis_stalled_notification_sent` SHALL be recorded with the elapsed duration
- **AND** `notifier.on_stalled_diagnosis(issue, elapsed_seconds)` SHALL be called if the notifier implements that method
- **AND** `issue.extras["stalled_notification_sent"]` SHALL be set to `True`

#### Scenario: Subsequent ticks do not re-notify
- **WHEN** the watchdog runs again for an issue whose `stalled_notification_sent` extra is `True`
- **THEN** the notification SHALL NOT be re-sent
- **AND** no new audit entry SHALL be logged

#### Scenario: Fresh DIAGNOSED below threshold — no-op
- **WHEN** an issue's `diagnosed_at` is less than `diagnosed_stall_hours` ago
- **THEN** no notification and no audit entry SHALL fire

#### Scenario: No notifier attached — audit-only
- **WHEN** the manager has no notifier configured
- **THEN** the audit entry SHALL still be recorded
- **AND** the watchdog SHALL NOT raise

#### Scenario: Notifier missing `on_stalled_diagnosis` — audit-only
- **WHEN** the notifier object does not implement `on_stalled_diagnosis`
- **THEN** the audit entry SHALL still be recorded
- **AND** the watchdog SHALL NOT raise

### Requirement: Low-confidence auto-fix escape (opt-in)

When `IssuesPolicyConfig.auto_fix_conditions["low_confidence_after_hours"]` is a positive number N, the policy engine SHALL permit auto-fix promotion for DIAGNOSED issues that: (a) have been DIAGNOSED for longer than N hours, AND (b) have `diagnosis.confidence >= 0.4`. When this escape fires, the promotion SHALL be recorded in audit as `low_confidence_auto_fix_approved` with the confidence value and elapsed hours.

#### Scenario: Escape disabled by default
- **WHEN** `low_confidence_after_hours` is None or 0
- **THEN** the policy engine SHALL NOT promote sub-min_confidence issues to FIXING regardless of elapsed time

#### Scenario: Escape fires — promote to FIXING
- **WHEN** `low_confidence_after_hours` is 1, elapsed > 1h, and `confidence >= 0.4`
- **THEN** the issue SHALL transition DIAGNOSED → FIXING (subject to concurrency limits)
- **AND** audit entry `low_confidence_auto_fix_approved` SHALL record confidence and elapsed

#### Scenario: Escape rejects too-low confidence
- **WHEN** `confidence < 0.4`
- **THEN** the escape SHALL NOT fire regardless of elapsed time

### Requirement: Investigator prompt recognises source corruption

The `INVESTIGATION_PROMPT` template SHALL include a "Source corruption recognition" section that instructs the agent to exit with a specific diagnosis when it detects duplicate top-level imports, repeated code blocks, or leftover merge markers in a read file.

#### Scenario: Corruption section present in prompt
- **WHEN** `INVESTIGATION_PROMPT` is rendered for any issue
- **THEN** the output SHALL include a subsection describing duplicate-imports / repeated-blocks / merge-marker patterns and the exit instruction

#### Scenario: Exit advice is specific
- **WHEN** the corruption section is rendered
- **THEN** it SHALL name the recommended diagnosis ("source corruption (duplicate blocks from bad merge/auto-fix)")
- **AND** it SHALL recommend the `git diff HEAD~1 -- <file>` verification step
- **AND** it SHALL explicitly permit emitting a partial diagnosis when the corruption blocks further analysis
