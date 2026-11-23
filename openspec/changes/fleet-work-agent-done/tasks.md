## 0. Precondition

- [ ] 0.1 `fleet-mandate-and-desk` has committed `mandate.py`, `mandate_cli.py` and `mandate_delivery.py`. This is agreed on the bus with the session applying it, because the files below are theirs while it is in flight.

## 1. Record

- [ ] 1.1 CORE `lib/set_orch/fleet/mandate.py`: `agent-done` joins `END_REASONS`. The inventory reports it as the agent's claim, with no fulfilment field. Test: ending with `agent-done` round-trips, and the payload carries no `fulfilled`.

## 2. Done step

- [ ] 2.1 CLI `lib/set_orch/fleet/mandate_cli.py`: the `done "<line>"` verb. It resolves the caller's own mandate the way `show` does, refuses anything that is not an open, agent-requested `work` mandate, then posts to the requester (bus), then calls `end(..., "agent-done")`, then stops its own label through `POST /api/fleet/agents/{label}/stop`. The order is load-bearing: the stop ends the caller.
- [ ] 2.2 Tests: the refusals (no mandate, desk, no requester), the order (a failed post ends nothing and stops nothing), and the happy path against a fake bus and a fake stop route. Mutate the order and confirm a test fails.

## 3. Delivery

- [ ] 3.1 `lib/set_orch/fleet/mandate_delivery.py`: the done-step line for agent-requested `work` mandates only. Test both directions.

## 4. Idle-close

- [ ] 4.1 `lib/set_orch/fleet/idle_close.py`: the work bound (`fleet_idle_close_work_hours`, default 2), counted from the last movement, for agents whose mandate is `work` with a requester and that have no owner input since their start. Unmeasured → keep. Busy → keep. Owner input after start → the ordinary rule. Tests in both directions for each.

## 5. Verify

- [ ] 5.1 Live: start a `work` agent through `set-fleet-ask` or the start route with a requester, have it run the done step, and check four things: the requester's room has the line, the mandate is ended with `agent-done`, the label is gone from the owner, and the roster lists the session.
- [ ] 5.2 Close B-205 in `openspec/bugs/README.md` with that evidence, and answer the reporter on the bus.
