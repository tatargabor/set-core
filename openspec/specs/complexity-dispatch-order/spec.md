## ADDED Requirements

### Requirement: Dispatch prioritizes larger changes within same dependency level
When multiple pending changes have satisfied dependencies, `dispatch_ready_changes()` SHALL dispatch larger complexity changes first.

#### Scenario: L and M changes both ready
- **WHEN** two changes with complexities L and M both have satisfied dependencies and there is one dispatch slot available
- **THEN** the L-complexity change SHALL be dispatched first

#### Scenario: Same complexity falls back to topological order
- **WHEN** two pending changes have the same complexity and both have satisfied dependencies
- **THEN** they SHALL be dispatched in topological (alphabetical) order as before

#### Scenario: Complexity field missing
- **WHEN** a change has no complexity field in the state
- **THEN** it SHALL be treated as M (medium) for dispatch ordering purposes
