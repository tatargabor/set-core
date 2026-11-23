## 0. Precondition

- [x] 0.1 `fleet-mandate-and-desk` has committed `mandate.py`, `mandate_cli.py` and `mandate_delivery.py`. This is agreed on the bus with the session applying it, because the files below are theirs while it is in flight.

## 1. Record

- [x] 1.1 CORE `lib/set_orch/fleet/mandate.py`: `agent-done` and `work-idle` join `END_REASONS`. The inventory reports it as the agent's claim, with no fulfilment field. Test: ending with `agent-done` round-trips, and the payload carries no `fulfilled`.

## 2. Done step

- [x] 2.1 CLI `lib/set_orch/fleet/mandate_cli.py`: the `done "<line>"` verb. It resolves the caller's own mandate the way `show` does, refuses anything that is not an open, agent-requested `work` mandate, then posts to the requester (bus), then calls `end(..., "agent-done")`, then stops its own label through `POST /api/fleet/agents/{label}/stop`. The order is load-bearing: the stop ends the caller.
- [x] 2.2 Tests: the refusals (no mandate, desk, no requester), the order (a failed post ends nothing and stops nothing), and the happy path against a fake bus and a fake stop route. Mutate the order and confirm a test fails.

## 3. Delivery

- [x] 3.1 `lib/set_orch/fleet/mandate_delivery.py`: the done-step line for agent-requested `work` mandates only. Test both directions.

## 4. Work sweep and the human-input measure

- [x] 4.1 CORE `lib/set_orch/fleet/work_close.py`: the decision, with every input that is not measured keeping the agent. API `lib/set_orch/api/fleet_work.py`: the sweep (stop through the owner, then end the mandate as `work-idle` only when the owner found the agent). One call added to `fleet_mandate.sweep_loop`, which is the peer's file; the peer is told on the bus.
- [x] 4.2 CORE `lib/set_orch/fleet/state.py`: `isMeta` turns and turns whose `origin.kind` is not `human` do not count as human input. Measured on this session's own transcript: 5 entries counted as human before the fix, 3 after (the 3 real messages).
- [x] 4.3 Tests: `tests/unit/test_fleet_work_agent_done.py`, 24 cases. Four mutations, each caught: the end before the stop, the `isMeta` guard, the quiet-only rule, and the takeover rule. Related fleet suites: 343 passed; the one failure (`test_a_rename_carries_the_record_and_the_layout`) also fails on HEAD.

## 5. Verify

- [ ] 5.1 Live (BLOCKED 2026-11-23: the running agent owner predates the mandate feature and refuses to carry one. Restarting it ends every agent it holds, and 12 were live, so it waits for the operator's OK): start a `work` agent through `set-fleet-ask` or the start route with a requester, have it run the done step, and check four things: the requester's room has the line, the mandate is ended with `agent-done`, the label is gone from the owner, and the roster lists the session.
- [ ] 5.2 Close B-205 in `openspec/bugs/README.md` with that evidence, and answer the reporter on the bus.
