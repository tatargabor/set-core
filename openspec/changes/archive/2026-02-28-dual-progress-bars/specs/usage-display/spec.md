## MODIFIED Requirements

### Requirement: Display Claude Capacity Statistics
The Control Center GUI SHALL display Claude Code capacity statistics via dual progress bars — a time-elapsed bar above a usage bar for each time window (5h session, 7d weekly).

#### Scenario: Dual bars displayed per time window
Given the Control Center is running
And usage data is available from the API
When the GUI refreshes
Then each time window (5h, 7d) SHALL display two bars stacked vertically with 0px gap:
  - Top bar: time-elapsed percentage (how far through the window)
  - Bottom bar: usage percentage (how much quota consumed)

#### Scenario: Display format with comma separator
Given usage data is available from the API
When displaying session usage
Then the time label SHALL show format like "60%, 2h" (time-elapsed percentage, comma, remaining time)
And the usage label SHALL show format like "42%" (usage percentage only)
And weekly time label SHALL show format like "71%, 2d" (time-elapsed percentage, comma, remaining time)
And weekly usage label SHALL show format like "55%" (usage percentage only)

#### Scenario: Local-only data shows unknown state
Given usage data comes from local JSONL parsing (no session key)
When displaying capacity
Then time labels SHALL show "--"
And usage labels SHALL show "--/5h" and "--/7d"
And all four progress bars SHALL remain empty
And tooltips show token counts and suggest setting session key

#### Scenario: Burn-rate-relative color coding
Given usage data is available from the API
When usage percentage is more than 5 points below time-elapsed percentage
Then the usage bar SHALL be displayed in green (under pace)
When usage percentage is within 5 points of time-elapsed percentage
Then the usage bar SHALL be displayed in yellow (on pace)
When usage percentage is more than 5 points above time-elapsed percentage
Then the usage bar SHALL be displayed in red (over pace)

#### Scenario: Time bar color
Given usage data is available from the API
When displaying the time-elapsed bar
Then the time bar SHALL use a neutral color (`bar_time` theme color) regardless of percentage

#### Scenario: Graceful fallback when data unavailable
Given usage data cannot be fetched from any source
When the GUI attempts to display capacity
Then it displays "--" for time labels and "--/5h", "--/7d" for usage labels
And all four bars remain empty
And does not show errors to the user

## ADDED Requirements

### Requirement: Time-Elapsed Percentage Calculation
The GUI SHALL calculate how far through each time window the user currently is, derived from the reset timestamp.

#### Scenario: Time-elapsed from reset timestamp
- **WHEN** the API returns a `session_reset` or `weekly_reset` ISO timestamp
- **THEN** the time-elapsed percentage SHALL be calculated as: `(now - (reset - window)) / window * 100`
- **AND** the result SHALL be clamped to 0-100%

#### Scenario: 5h session window
- **WHEN** calculating time-elapsed for the session bar
- **THEN** the window size SHALL be 5 hours

#### Scenario: 7d weekly window
- **WHEN** calculating time-elapsed for the weekly bar
- **THEN** the window size SHALL be 7 days (168 hours)

### Requirement: Time Bar Theme Color
A new `bar_time` color SHALL be added to all theme color profiles.

#### Scenario: Theme color values
- **WHEN** rendering the time-elapsed bar
- **THEN** the bar color SHALL use `bar_time` from the active theme
- **AND** `bar_time` SHALL be a muted neutral tone (slate/gray family) in all themes
