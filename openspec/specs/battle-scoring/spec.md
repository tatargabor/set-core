# Battle Scoring Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Point scoring derived from real orchestration metrics
- Achievement system with unlock conditions based on orchestration events
- Score multipliers for parallel execution and streaks
- Lives system tied to failure count
- Persistent high scores per project in localStorage

### Out of scope
- Server-side score storage or leaderboards
- Cross-project score comparison
- Configurable scoring rules (hardcoded for simplicity)

## Requirements

### Requirement: Score Calculation
The scoring system SHALL award points based on real orchestration events:

| Event | Points |
|-------|--------|
| Change completed (first try) | +1000 |
| Change completed (after retry) | +500 |
| Change completed (after 2+ retries) | +250 |
| Verify gate passed first attempt | +300 |
| Build gate passed | +100 |
| Test gate passed | +100 |
| Review gate passed | +100 |
| Token efficiency (<50k tokens) | +500 bonus |
| Token efficiency (<100k tokens) | +200 bonus |
| Fast completion (<5 min) | +300 bonus |
| Change failed | -200 |
| Change stalled >5min | -100 |
| Context overflow (>80%) | -50 |

#### Scenario: Change completes first try with low token usage
- **WHEN** a change transitions to `done` with 0 previous failures and <50k total tokens
- **THEN** the score MUST increase by 1000 + 300 (verify) + 500 (token bonus) = 1800 points

#### Scenario: Change fails then recovers
- **WHEN** a change fails once (-200), then completes on retry (+500, +300 verify)
- **THEN** the net score change MUST be +600 points

### Requirement: Score Multiplier
Active multipliers SHALL apply to all point gains (not penalties):
- **2x** when 2 changes are running in parallel
- **3x** when 3 or more changes are running in parallel
- **1.5x** phase streak bonus (all changes in current phase completed with 0 failures)

Multipliers stack multiplicatively.

#### Scenario: Parallel execution bonus
- **WHEN** 3 changes are running and one completes (first try, +1000 base)
- **THEN** the score gain MUST be 1000 × 3 = 3000 points

#### Scenario: Stacked multipliers
- **WHEN** 2 changes are running (2x) and phase streak is active (1.5x) and a change completes first try
- **THEN** the score gain MUST be 1000 × 2 × 1.5 = 3000 points

### Requirement: Lives System
The battle view SHALL display 3 lives (♥♥♥). One life is lost for every 3 cumulative change failures. When all lives are lost, a "Game Over" overlay MUST appear — but with a "Continue?" button that resets lives.

#### Scenario: Third failure occurs
- **WHEN** the total failure count reaches 3 (or 6, 9, etc.)
- **THEN** one life MUST be removed from the display

#### Scenario: All lives lost
- **WHEN** the third life is lost
- **THEN** a "Game Over" overlay MUST appear with the final score and a "Continue?" button

#### Scenario: Continue after game over
- **WHEN** the user clicks "Continue?"
- **THEN** lives MUST reset to 3 and the score MUST continue (not reset)

### Requirement: Achievements
The system SHALL support unlockable achievements based on orchestration events. Achievements MUST be displayed as a bar at the bottom of the battle view (locked = gray, unlocked = colored).

When an achievement unlocks, a pop-up notification MUST appear for 3 seconds.

| Achievement | Condition | Rarity |
|-------------|-----------|--------|
| First Blood | First change completed | Common |
| Speed Demon | Any change completed in <5 minutes | Rare |
| Flawless | Any change: 0 failures, 0 retries | Uncommon |
| Marathon Man | Orchestration running >2 hours | Common |
| Token Miser | Any change completed with <50k tokens | Rare |
| Token Whale | Total tokens exceed 10M | Uncommon |
| On Fire | 3 consecutive changes completed first-try | Rare |
| Rage Quit | User manually stops orchestration | Legendary |
| Clean Sweep | All changes done with 0 total failures | Epic |
| Perfect Run | Clean Sweep + Token Miser on every change | Legendary |
| Bug Squasher | 5+ failed changes that eventually completed | Uncommon |
| Phase Complete | All changes in a phase completed | Common |
| Parallel Power | 3+ changes running simultaneously | Uncommon |
| Coffee Break | Dashboard tab inactive for 15+ minutes | Common |
| Comeback Kid | A change that failed 2+ times then completed | Rare |

#### Scenario: Achievement unlocks
- **WHEN** the conditions for an achievement are met
- **THEN** a pop-up MUST appear showing the achievement name, description, bonus points, and rarity

#### Scenario: Achievement persistence
- **WHEN** achievements are unlocked
- **THEN** they MUST be saved to localStorage keyed by project name

### Requirement: Score Persistence
High scores MUST be stored in localStorage per project. The battle view MUST display the current score and the project's high score.

#### Scenario: New high score
- **WHEN** the current score exceeds the stored high score for this project
- **THEN** the high score MUST be updated and a "NEW HIGH SCORE!" indicator MUST appear

#### Scenario: Score display
- **WHEN** the battle view is rendered
- **THEN** the current score, high score, and current multiplier MUST be visible in the header area
