# Measurements — fleet-agent-identity

Everything here was run, not recalled. Where a claim has no command beside it, it is
marked as an assumption.

## M1 — the name the record stored, before and after

Before (measured on the live record after the first real reboot, 2026-08-21): the entry for
session `039178b5…` carried `set-core-c6`, a runtime-derived name, for an agent its user had
named `set-core-bugfix`. `roster._entry_from` read `agent.name`, and `discovery` fills that
from `~/.claude/sessions/<pid>.json`, field `name`, `nameSource: "derived"`.

After (`~/.local/share/set-core/fleet-roster.json`, once the service picked up the change):

    039178b5  label= set-core-34
    7dee9992  label= set-core-bb
    13da096d  label= set-core-e2
    …

Every set-core entry carries the framework's label; none carries a derived name. An agent the
framework does not hold is recorded with `label: null`.

## M2 — the collision that reached the screen

`GET /api/fleet/agents`, 2026-08-21: pid 54272 was NAMED `set-core-33` while pid 43704's
terminal LABEL was `set-core-33`. Two agents, one string, every control keyed on the label.

After: every held agent's `name` equals its `terminal_label`, the runtime's string moved to
`runtime_name`, and a foreign agent whose runtime name collides with a held label is shown
with its pid. Verified on the same endpoint — 9 agents, no collision.

## M3 — five call sites derive a unit from a label; one of them was the hazard

`grep -rn "unit_name(\|_as_scope(" lib bin modules` → 5 in product code. Four are start-time
or take a unit already in hand. The fifth is `owner.stop()`'s else-branch, which derives when
it holds no agent under that label — right for an ORPHAN, and after a rename it would derive
the RUNNING agent's unit and stop it while reporting it foreign.

## M4 — the owner service runs the code it started with

Measured live, 2026-08-21, through the screen: a rename came back
`unknown method 'rename'; this owner answers attach, detach, health, list, orphans, recover,
resize, start, stop, tail, write`. The daemon has been up since 22:14 and holds 9 agents;
`systemctl --user show set-agent-owner -p ExecMainStartTimestamp` is the check.

**Restarting it ends every agent it holds** — its own measurement: a pty-attached agent dies
when its pty holder dies, and the service logs `SIGTERM received; N held agent(s) will end
with this process`. So the rename cannot be exercised on the running fleet without that
restart, and the four tasks that depend on it stay open rather than being marked done.

## M5 — two defects only LOOKING found

Both after 105 python and 782 web tests were green:

- the tile header read `set-core-memory [set-core-memory] rename cancel` — the same string
  twice, one of them editable. No structural test calls that wrong;
- an owner refusal is a sentence, and inline it pushed the state line and the rest of the
  header down the tile.

Also verified in the browser, because the edit lives in component state while the fleet polls
every few seconds: the field survives a poll (counter advanced 1s → 3s, input intact).

## M6 — the regression this change introduced, and how it was found

Not by any suite. By the baseline set-diff prescribed in `CLAUDE.md`: a worktree at
`a7e5b5de` with `PYTHONPATH` at its own roots and a session-end leak assertion.

    only in NOW: 11 failures — 10 in test_status_follow_stream.py, 1 in test_web_websocket.py

Two files this change never touches, every one green when its own file runs alone. Cause:
two new tests called `asyncio.run`, which clears the thread's ambient event loop. The file
already had `_run()` for exactly this, with a guard test — which stayed green, because it
proves the helper is safe and not that anyone calls it. Fixed, and the second guard asserts
the thing (`ast`, no `asyncio.run` CALL in the file).

**The final comparison is incomplete, and the reason is worth stating rather than hiding.**
A parallel session is removing the memory subsystem in this same tree, so `test_run_memory.py`
and four `test_hook_*.py` files stop at collection and abort the whole run. Excluding those
five on both sides: **77 failed / 4085 passed, and the diff against the baseline is empty** —
no test regression. (Two apparent additions are logger lines, not test ids: the
`^(FAILED|ERROR) ` pattern the repo's own recipe uses also matches log output, and one such
line moved by 14 lines when another session edited `dispatcher.py`.)
