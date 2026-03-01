## MODIFIED Requirements

### Requirement: Display Claude Capacity Statistics
The Control Center GUI SHALL display Claude Code capacity statistics via dual progress bars — a usage bar above a time-elapsed bar for each time window (5h session, 7d weekly).

#### Scenario: Dual bars displayed per time window
Given the Control Center is running
And usage data is available from the API
When the GUI refreshes
Then each time window (5h, 7d) SHALL display two bars stacked vertically with 0px gap:
  - Top bar: usage percentage (how much quota consumed)
  - Bottom bar: time-elapsed percentage (how far through the window)

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
When usage percentage is below time-elapsed percentage
Then the usage bar SHALL be displayed in green (under budget)
When usage percentage is equal to or above time-elapsed percentage
Then the usage bar SHALL be displayed in red (over budget)

#### Scenario: Time bar color
Given usage data is available from the API
When displaying the time-elapsed bar
Then the time bar SHALL use a light gray color (`bar_time` theme color) regardless of percentage

#### Scenario: Graceful fallback when data unavailable
Given usage data cannot be fetched from any source
When the GUI attempts to display capacity
Then it displays "--" for time labels and "--/5h", "--/7d" for usage labels
And all four bars remain empty
And does not show errors to the user

#### Scenario: Burn rate color without time data
Given usage data is available but time-elapsed percentage is unknown
When usage percentage is below 80%
Then the usage bar SHALL be displayed in green
When usage percentage is 80% or above
Then the usage bar SHALL be displayed in red
