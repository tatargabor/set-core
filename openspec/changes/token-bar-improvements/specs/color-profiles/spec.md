## MODIFIED Requirements

### Requirement: Preset Color Profiles
The system SHALL provide four preset color profiles: light, gray (default), dark, and high_contrast. Each profile SHALL define all semantic color keys used by the application, including `text_secondary` and `text_primary`.

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
