# Issue Policy Engine

## ADDED Requirements

## IN SCOPE
- Policy configuration via YAML (manager.yaml or orchestration.yaml)
- Mode-based policy overrides (e2e, production, development)
- Auto-fix eligibility evaluation (confidence, scope, tags)
- Timeout calculation per severity and mode
- Always-manual rules
- Registration filtering (which detection events become issues)
- Mute pattern matching with TTL

## OUT OF SCOPE
- Runtime policy editing via API (read-only from config)
- Machine learning-based policy adaptation
- Per-project custom policies (mode-level is the granularity)

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
