## Context

A gap reason is a sentence about the agent. `nothing-started` says "this agent is not on
a change"; `join-failed` says "we looked and could not tell". The resolver decided
between them with a question about the project ("does any change directory exist?"),
which is answered *yes* in every project that does not archive aggressively.

## Decisions

- **Evidence of absence vs absence of evidence.** If the agent's own session record was
  readable and contained no change invocation, and no running work-cycle record binds
  the agent, then we did look and the agent addresses no change: `nothing-started`. If
  the record could not be read, we could not look: the old project-level test still
  decides, because then it is the only evidence there is.
- **The declared path follows the same rule.** A populated producer index says the
  project has work in flight, not that this agent is on any of it. A named change that
  the index does not carry stays `join-failed` — that one is a real failed match.
- **No new reason value.** The payload contract keeps its four reasons; only the
  selection changes, so no consumer of the field needs to change.

## Risks / Trade-offs

- An agent that IS working a change but whose transcript never addresses it by an
  invocation shape (and that has no running engine record) now reads as idle rather
  than unmatched — the calm direction. Measured on the day: no live agent was in that
  position, and orchestration agents carry a running work-cycle record or a
  `change/<name>` branch reference. If it turns up, the fix is a better join, not a
  project-wide alarm.
