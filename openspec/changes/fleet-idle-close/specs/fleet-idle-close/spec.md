## IN SCOPE
- Choosing which interactive fleet agents are idle long enough to close
- Closing them through the fleet's existing stop route, with a dry run
- A local record of every close
- A daily schedule the owner installs explicitly

## OUT OF SCOPE
- Bringing an agent back: the existing roster restore does that, unchanged
- Agents the fleet did not start (no terminal label): the stop route cannot reach them
- Orchestration workers and anything that is not an interactive session
- Deciding on token cost or context size: the only signal is the owner's last input

## ADDED Requirements

### Requirement: Only long-idle interactive agents are closed

The command SHALL close an agent only when all of these hold: it is an interactive session, the
fleet started it (it has a terminal label), and its time since the last human input is a measured
number greater than the threshold. The threshold SHALL default to 48 hours and SHALL be read from
local config `fleet_idle_close_hours`, which a command-line option overrides.

#### Scenario: An agent idle past the threshold is closed
- **WHEN** an interactive, fleet-started agent's last human input was 60 hours ago and the threshold is 48 hours
- **THEN** the command closes it

#### Scenario: An agent used recently is kept
- **WHEN** an agent's last human input was 10 hours ago
- **THEN** the command keeps it, even if it has not moved for longer

#### Scenario: Movement without the owner does not count as use
- **WHEN** an agent's last human input was 60 hours ago but a watch woke it 5 minutes ago
- **THEN** the command closes it, because waking on its own is exactly the cost being removed

### Requirement: Doubt keeps the agent

The command SHALL keep an agent whose idle time is not measured, and an agent that is running a
tool at that moment, and SHALL say which ones it kept for that reason. An agent without a terminal
label SHALL be listed as not reachable, never stopped by other means.

#### Scenario: Unmeasured idle time
- **WHEN** an agent's time since the last human input is unknown
- **THEN** it is kept and reported as unmeasured

#### Scenario: Busy at the moment
- **WHEN** an idle-long agent is in the middle of a tool call
- **THEN** it is kept and reported as busy; a later run may close it

### Requirement: A dry run closes nothing

With `--dry-run` the command SHALL report every agent it would close and why, and SHALL send no
stop request.

#### Scenario: Dry run
- **WHEN** the command runs with `--dry-run` and two agents qualify
- **THEN** both are listed and no stop request is sent

### Requirement: Every close is recorded

Each agent the command closes SHALL be appended to a local log outside every repository, with the
time, label, project, session id and idle hours, so the owner can find it in the roster and bring
it back. A stop the fleet refuses or cannot find SHALL be reported as a failure, never as closed.

#### Scenario: A close is logged
- **WHEN** the command closes an agent
- **THEN** one line naming it and its session id is appended to the log

#### Scenario: A refused stop is not a close
- **WHEN** the stop route answers 404 for an agent
- **THEN** the run reports that agent as failed and writes no close record for it

### Requirement: The schedule is installed on purpose

`install-timer` SHALL write a daily systemd user service and timer that run the command, and
enable the timer. Without it the command SHALL never run on its own.

#### Scenario: Installing the timer
- **WHEN** the owner runs `set-fleet-idle-close install-timer`
- **THEN** a daily user timer exists and is enabled, and its service runs the command
