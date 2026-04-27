# Issue Policy Engine

## Purpose

Decide how each detected anomaly enters the issue lifecycle: whether it registers as an issue at all, what severity and timeout apply, whether auto-fix is eligible, and which conditions force manual approval. Policy is configured via YAML with mode-based overrides (e2e, production, development); evaluation is deterministic and read-only at runtime.

### In scope
- Policy configuration via YAML (manager.yaml or orchestration.yaml)
- Mode-based policy overrides (e2e, production, development)
- Auto-fix eligibility evaluation (confidence, scope, tags)
- Timeout calculation per severity and mode
- Always-manual rules
- Registration filtering (which detection events become issues)
- Mute pattern matching with TTL

### Out of scope
- Runtime policy editing via API (read-only from config)
- Machine learning-based policy adaptation
- Per-project custom policies (mode-level is the granularity)
## Requirements
### Requirement: Policy configuration loading
The policy engine SHALL load configuration from YAML under the `issues:` key. Configuration SHALL include timeout_by_severity, modes overrides, auto_fix_conditions, always_manual rules, investigation settings, retry settings, and concurrency limits.

#### Scenario: Mode override applied
- **WHEN** a project runs in e2e mode and policy is evaluated for a medium severity issue
- **THEN** the e2e mode's timeout (120s) is used instead of the default (300s)

### Requirement: Auto-fix eligibility
The policy engine SHALL evaluate whether an issue can be auto-fixed based on: severity is in auto_fix_severity for the mode, confidence >= min_confidence, fix_scope <= max_scope, no blocked_tags present, and no always_manual rule matches.

#### Scenario: Eligible for auto-fix
- **WHEN** a diagnosed issue has confidence=0.9, severity=medium, scope=single_file, no blocked tags, in e2e mode
- **THEN** policy returns can_auto_fix=True

#### Scenario: Blocked by tag
- **WHEN** a diagnosed issue has tags=["db_migration"] which is in blocked_tags
- **THEN** policy returns can_auto_fix=False regardless of other conditions

#### Scenario: Unknown severity blocks auto-fix
- **WHEN** an issue has severity="unknown" (not yet investigated)
- **THEN** policy returns can_auto_fix=False (must investigate first)

### Requirement: Timeout calculation
The policy engine SHALL calculate approval timeout based on issue severity and project mode. A timeout of 0 means instant auto-fix. A timeout of null means never auto-approve (always manual).

#### Scenario: Instant auto-fix
- **WHEN** severity=low in e2e mode with timeout=0
- **THEN** the issue goes directly to FIXING with no AWAITING_APPROVAL phase

#### Scenario: Never auto-approve
- **WHEN** severity=critical in production mode with timeout=null
- **THEN** the issue stays in DIAGNOSED until manual action

### Requirement: Registration filtering
The policy engine SHALL filter which detection events become issues. Sentinel findings with severity=info SHALL be excluded. Muted patterns SHALL be checked before registration.

#### Scenario: Info finding filtered
- **WHEN** a sentinel finding with severity=info is detected
- **THEN** it is not registered as an issue

#### Scenario: Muted error filtered
- **WHEN** a new error matches a mute pattern
- **THEN** the mute pattern's match_count is incremented and no issue is registered

### Requirement: Config schema includes investigation.max_turns

`IssuesPolicyConfig.investigation` (dataclass `InvestigationConfig`) SHALL include a `max_turns: int` field with default value 40.

#### Scenario: Default value
- **WHEN** `InvestigationConfig()` is constructed with no arguments
- **THEN** the `max_turns` field SHALL equal 40

#### Scenario: Field is loaded from YAML via from_dict
- **WHEN** `IssuesPolicyConfig.from_dict({"investigation": {"max_turns": 30}})` is called
- **THEN** the resulting config's `investigation.max_turns` SHALL equal 30

### Requirement: Config schema includes diagnosed_stall_hours

`IssuesPolicyConfig` SHALL include a top-level `diagnosed_stall_hours: int` field with default 2.

#### Scenario: Default value
- **WHEN** `IssuesPolicyConfig()` is constructed with no arguments
- **THEN** the `diagnosed_stall_hours` field SHALL equal 2

#### Scenario: Field is loaded from YAML via from_dict
- **WHEN** `IssuesPolicyConfig.from_dict({"diagnosed_stall_hours": 1})` is called
- **THEN** the resulting config's `diagnosed_stall_hours` SHALL equal 1

### Requirement: auto_fix_conditions supports low_confidence_after_hours

`IssuesPolicyConfig.auto_fix_conditions` SHALL recognise an optional `low_confidence_after_hours` key. When set to a positive integer N, the policy engine SHALL permit auto-fix of DIAGNOSED issues whose `diagnosed_at` is older than N hours AND whose diagnosis confidence is ≥ 0.4. When absent or None, behavior is unchanged (the escape does not fire).

#### Scenario: Default omits the escape
- **WHEN** `IssuesPolicyConfig()` is constructed with defaults
- **THEN** `auto_fix_conditions` SHALL contain the existing keys (`min_confidence`, `max_scope`, `blocked_tags`)
- **AND** SHALL NOT contain a non-None `low_confidence_after_hours` value (the key may be absent or None)

#### Scenario: Explicit opt-in
- **WHEN** `from_dict` receives `auto_fix_conditions: {low_confidence_after_hours: 1}`
- **THEN** the config SHALL store that value and the policy engine SHALL honor it in subsequent decisions

