## MODIFIED Requirements

### Requirement: Layout structure (CHANGED)
Previously two rows per group (time label + time bar, usage label + usage bar). Now one row per group (combined label + DualStripeBar).

#### Scenario: Usage area layout
- **WHEN** the Control Center window is displayed
- **THEN** each usage group (5h, 7d) occupies a single horizontal row
- **AND** the row contains a combined label (90px wide) and a DualStripeBar (stretch)
- **AND** both groups sit side by side with 15px spacing

### Requirement: Height calculation (CHANGED)
The `other_height` constant must reflect the reduced usage area.

#### Scenario: Window height adjustment
- **WHEN** `adjust_height_to_content()` is called
- **THEN** the `other_height` accounts for ~22px usage area (down from ~43px)
