## Context

The fleet listing (`GET /api/fleet/agents`) already measures, per agent, `last_human_input_seconds`
and `last_movement_seconds`, and the stop route (`POST /api/fleet/agents/{label}/stop`) stops a
framework-started agent by label and answers 404 when it holds no such agent. The roster records
every seen session and restores it later. What is missing is only the decision and the schedule.

## Goals / Non-Goals

**Goals:** close abandoned interactive agents daily; never close one that is in use or whose state
is unknown; leave a record good enough to bring each one back.

**Non-Goals:** a UI for it; a cost model; restoring (the roster does it).

## Decisions

- **The signal is the owner's last input, not the last movement.** Measured on the live fleet the
  day this was asked for: every idle agent had moved within the last hour, because watches and bus
  messages wake it. Movement is the cost, so it cannot be the evidence of use.
- **Go through the running dashboard, not the owner socket directly.** The listing is what computes
  the idle figures, and the stop route already carries the 404 rule. A second path to stop would
  be a second place for that rule to drift. If the dashboard is down, the run fails loudly and
  closes nothing.
- **Fail toward keeping.** Unknown idle time, a running tool, or a missing label each keep the
  agent. A wrongly kept agent costs tokens until the next run; a wrongly closed one interrupts the
  owner's work.
- **The schedule is opt-in.** The framework is shared; a command that silently stops other people's
  sessions on install would be a surprise. `install-timer` is the explicit act.
- **The log is local state** (`$XDG_STATE_HOME/set-core/fleet-idle-close.jsonl`), because it names
  sessions and projects.

## Risks / Trade-offs

- [An agent working unattended for days on purpose is closed] → it is kept while a tool is
  running; between tool calls it can be closed, and it is resumable from the roster.
- [The dashboard's idle figure is wrong] → an unmeasured figure keeps the agent; a wrong number is
  the listing's defect, not this command's, and is visible in the log.
