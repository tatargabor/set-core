## 1. Resolver (Layer 1: lib/set_orch)

- [x] 1.1 `resolve_stage`, derived path: an unjoined agent whose session record was read is `nothing-started`; an unreadable record falls back to the project-level test
- [x] 1.2 `resolve_stage`, declared path: the same rule for an unjoined agent; a named change missing from the index stays `join-failed`

## 2. Tests

- [x] 2.1 Derived: a readable record with no invocation in a project with an active change → `nothing-started` (red on the unfixed source)
- [x] 2.2 Declared: the same against a populated index (red on the unfixed source)
- [x] 2.3 Existing gap tests stay green: unreadable record + active change → `join-failed`; name missing from the index → `join-failed`

## 3. Surface (web/src)

- [x] 3.1 Tooltip text for the empty and `join-failed` states says what each means about the agent

## 4. Ship

- [x] 4.1 Stage suites and the strip's unit tests green
- [x] 4.2 Dashboard service restarted; `GET /api/fleet/agents` no longer reports `join-failed` for agents addressing no change
- [x] 4.3 Looked at the fleet panel in the browser: idle agents show the quiet `—`
- [x] 4.4 B-169 closed with the commit
