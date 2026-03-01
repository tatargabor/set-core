# color-profiles Specification

## Purpose
TBD - created by archiving change add-color-profiles. Update Purpose after archive.
## Requirements
### Requirement: Color Profile Selection
The Control Center SHALL support multiple color profiles (themes) that can be selected from the config dialog.

#### Scenario: User selects dark profile
Given the Control Center is running with light profile
When the user opens config dialog and selects "dark" profile
Then all UI colors change to dark theme variants
And the selection is persisted for next launch

### Requirement: Preset Color Profiles
The system SHALL provide four preset color profiles: light, gray (default), dark, and high_contrast. Each profile SHALL define all semantic color keys used by the application, including `text_secondary` and `text_primary`.

#### Scenario: Light profile colors
Given the color profile is set to "light"
Then status_running color is green (#22c55e)
And status_waiting color is orange (#f59e0b)
And bar_background is light gray (#e5e7eb)
And text_secondary is blue (#60a5fa)
And text_primary is dark gray (#1f2937)

#### Scenario: Dark profile colors
Given the color profile is set to "dark"
Then status_running color is lighter green (#4ade80)
And status_waiting color is lighter orange (#fbbf24)
And bar_background is dark gray (#374151)
And text_secondary is blue (#60a5fa)
And text_primary is near-white (#f9fafb)

#### Scenario: High contrast profile colors
Given the color profile is set to "high_contrast"
Then text_primary is white (#ffffff)
And text_secondary is bright blue (#00aaff)
And bg_dialog is very dark (#222222)

#### Scenario: Light profile bar_time color
Given the color profile is set to "light"
Then bar_time color SHALL be light gray (#d1d5db)

#### Scenario: Dark profile bar_time color
Given the color profile is set to "dark"
Then bar_time color SHALL be medium gray (#4b5563)

#### Scenario: Gray profile bar_time color
Given the color profile is set to "gray"
Then bar_time color SHALL be medium gray (#6b7280)

#### Scenario: High contrast profile bar_time color
Given the color profile is set to "high_contrast"
Then bar_time color SHALL be gray (#888888)

### Requirement: Semantic Color Names
All colors SHALL be referenced by semantic names (e.g., "status_running", "burn_high") rather than hardcoded hex values.

#### Scenario: Color lookup
Given a component needs the running status color
When it calls get_color("status_running")
Then it receives the hex color for the active profile

### Requirement: Row Background Colors by Status
Table rows SHALL have background colors based on worktree status.

#### Scenario: Running worktree row
Given a worktree has status "running"
Then its row background is gray (row_running color)

#### Scenario: Waiting worktree row not blinking
Given a worktree has status "waiting"
And it is not in the needs_attention set
Then its row background is yellow (row_waiting color)

#### Scenario: Waiting worktree row blinking
Given a worktree has status "waiting"
And it is in the needs_attention set
When blink state is on
Then its row background is red (row_waiting_blink color)
When blink state is off
Then its row background is transparent

#### Scenario: Idle worktree row
Given a worktree has status "idle"
Then its row background is transparent (row_idle color)

### Requirement: Complete Color Key Coverage
Every color key referenced by `get_color()` in the application code SHALL be defined in all color profiles. The fallback value `#000000` SHALL NOT be relied upon for any production color key.

#### Scenario: text_secondary is defined in all profiles
- **WHEN** `get_color("text_secondary")` is called
- **THEN** a themed color value is returned for any active profile
- **AND** the value is never the `#000000` fallback

#### Scenario: text_primary is defined in all profiles
- **WHEN** `get_color("text_primary")` is called
- **THEN** a themed color value is returned for any active profile
- **AND** the high_contrast profile returns a light color suitable for dark backgrounds

