## Why

Three skill-tracking hooks (`set-hook-skill`, `set-hook-activity`, `set-hook-stop`) are wired in
~48 projects and spawn a process on every prompt, Skill call and Stop, but a 30-day usage audit
found no reader of what they record. The git-based messaging path (`.set-control` worktree, the
`set-control*` bins and the MCP tools `send_message`, `get_inbox`, `get_activity`,
`get_team_status`, `get_ralph_status`, `get_worktree_tasks`, `list_worktrees`) exists in no
registered project; the live bus is set-agent-comm. Stage 3 of `fleet-era-consolidation`.

## What Changes

- Unwire the three skill-tracking hooks from the deploy (and remove them from consumers through
  the hook deploy's own provenance), after the reader check below.
- Remove the git-bus MCP tools from the set-core MCP server and the `set-control*` bins.
  **BREAKING** for any caller of those tools (16 calls in 30 days, all reaching a path no project
  has).

## Precondition (measure first, do not assume)

- Grep every reader of the skill-timestamp / activity files (dashboard activity API, fleet
  context). If one exists, the hook stays and this change narrows to the git bus.
- After the change, the fleet view still shows per-agent activity.

## Capabilities

### Modified Capabilities
- `project-init-deploy`: three hooks fewer per consumer.

## Impact

`bin/set-hook-{skill,activity,stop}`, `bin/set-deploy-hooks`, `bin/set-control*`, the MCP server
tool list, consumer `.claude/settings.json` on the next init.
