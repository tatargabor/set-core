## Context

The decider is the relay's outbound (`set-auto-answer`). It knows the asking session's id
and working directory from the relay's variables. The fleet knows its terminals by label, and
the owner daemon maps a label to the agent pid. The runtime's session record
(`~/.claude/sessions/<pid>.json`) maps the pid to the current session id.

## Decisions

**D1 — Name the terminal, not the session.** The owner's words are "the agent I am at", and
he works in one terminal across `/clear`s, each of which gives a new session id. So the opt-out
is `label:<label>`, resolved at decision time: session id → the owner's agent whose session
record carries it → its label. A session outside the fleet has no label, so it is named
`session:<id>`. Alternative: key by session id only. Rejected, because an automatic clear would
silently turn the decider back on in the middle of the planning it was turned off for.

**D2 — Off means the switch-off path, per agent.** The outbound already has a byte-for-byte
forward for the switch off. The opt-out takes that branch for one agent, so the channel sees
exactly what it sees with the switch off. Nothing new is invented on the operator's side.

**D3 — `here` finds its own session by walking up the process tree.** A `!` command runs
under the agent's process. The first ancestor with a session record is the agent, and its
session id gives the label through the owner. Nothing has to be typed.

**D4 — Stored in machine-local config.** `auto_answer.off_agents` sits beside the switch,
readable with `set-config get`, and never in a repository.

## Risks / Trade-offs

- [The owner daemon is down when the decider asks for the label] → only `session:` entries can
  match, and the decider logs that the label could not be resolved. A label opt-out then does
  not hold. That is the calm direction, so the log line says so at WARNING.
- [A label is renamed] → the opt-out follows the old name. The panel lists entries by name, so
  the stale one is visible and removable.
