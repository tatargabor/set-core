## ADDED Requirements

### Requirement: The header names the projects the relay cannot reach

The relay payload SHALL carry `unwired`: every registered, non-archived project whose
directory exists and whose settings — the project's `.claude/settings.json`, its
`.claude/settings.local.json`, or the user-level `~/.claude/settings.json` — do not wire
`set-hook-question-relay` as a `PreToolUse` hook whose matcher covers `AskUserQuestion`, or
`set-hook-wait-detect` as a `Stop` hook, each entry naming the project and which hooks are
missing. A settings file that cannot be parsed SHALL count as wiring nothing. `ready` SHALL
keep its meaning. While the relay is on and the list is not empty, the closed fleet header
SHALL show the count, the switch's title SHALL NOT describe the relay as reaching every
agent, and the relay detail SHALL list each project with its missing hooks. A payload
without the field SHALL render as an empty list.

#### Scenario: A project with a hand-authored hook chain

- **WHEN** the relay is on and one registered project's settings wire neither hook
- **THEN** the payload's `unwired` names that project with both hooks missing, and the closed
  header shows 1 unwired project

#### Scenario: Wired at user level

- **WHEN** the user-level settings wire both hooks
- **THEN** no project is listed as unwired

#### Scenario: Relay off

- **WHEN** the relay is off and a project is unwired
- **THEN** the closed header shows no unwired marker
