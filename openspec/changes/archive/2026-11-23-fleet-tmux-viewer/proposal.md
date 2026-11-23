## Why

A held agent can start a child agent with `tmux new-session -d …`. Measured on 2026-11-23, that
child was unreachable from the fleet in two ways:

- **It had no terminal.** The fleet attaches only to a pty its owner holds, so a session someone else
  started is `foreign`. The child sat on an AskUserQuestion for more than two hours, and nobody saw it.
- **It was reported as `orphaned`, which is a false value in the destructive direction.** The tmux server
  forks inside the caller's cgroup, so the child lived in the PARENT's framework scope. The listing reads
  the scope from the process's cgroup and offered a recovery whose first step is stopping that scope. That
  step would have killed the live parent.

## What Changes

- A process in a scope the owner currently holds is no longer reported `orphaned`. It is `foreign`.
- `recover` refuses a unit the owner holds before it stops anything.
- A `foreign` agent that is measured to run inside a tmux pane carries a `tmux` field. The tile then offers a
  **viewer**: the owner runs `tmux attach-session -t <pane>` on a pty it holds, and the fleet opens that pty
  like any held terminal (`POST /api/fleet/agents/{pid}/tmux-view`).
- The agent stays `foreign` everywhere: the population, the card edge, the displayed name and idle-close
  all keep treating it as foreign. The terminal's stop control says that it ends only the viewer.

## Capabilities

### New Capabilities
- `fleet-tmux-viewer`: watching and typing into a foreign agent that runs inside tmux, through an
  owner-held `tmux attach` viewer, and keeping a child of a held agent from being reported as an orphan.

## IN SCOPE
- Detecting a tmux pane for a foreign agent, with the inherited-environment case refused
- Starting, reusing and labelling the viewer through the existing owner start path
- The listing's orphan decision for processes inside held scopes, and the matching recover guard
- The surface: the offer, the honest stop wording, the shown name, idle-close

## OUT OF SCOPE
- Adopting or moving the agent into a framework pty. That is still impossible, and nothing here pretends otherwise.
- Terminal multiplexers other than tmux (screen, zellij)
- Starting child agents differently, which is the parent project's own choice
