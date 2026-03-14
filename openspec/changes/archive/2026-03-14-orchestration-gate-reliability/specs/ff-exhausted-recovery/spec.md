## MODIFIED Requirements

### Requirement: FF exhausted fallback tasks.md generation
The Ralph loop SHALL generate a minimal `tasks.md` when the ff retry limit is exceeded, instead of stalling. The ff→apply chaining condition is specified separately in `gate-ff-apply-chaining` spec.

#### Scenario: Chaining condition delegates to gate-ff-apply-chaining
- **WHEN** the ff→apply chaining logic is evaluated
- **THEN** the system SHALL use the action transition detection defined in `gate-ff-apply-chaining` spec (pre_action == ff:* AND post_action == apply:*)
