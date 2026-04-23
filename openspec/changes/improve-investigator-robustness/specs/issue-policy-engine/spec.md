## ADDED Requirements

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
