Documented after the fact: the code shipped as `7d700013` while a peer session was waiting on the shared
files. Each task names its evidence.

## 1. Orphan decision

- [x] 1.1 `_terminal_population` in `lib/set_orch/api/fleet.py`: a scope the owner holds is not an orphan.
      Evidence: `test_a_child_in_a_held_scope_is_not_reported_orphaned` (both directions). It fails when
      the guard is mutated out. Live: the desktape child went from `orphaned` to `foreign`.
- [x] 1.2 `recover` refuses a held unit before stopping (`lib/set_orch/fleet/owner.py`).
      Evidence: `test_recover_refuses_a_scope_the_owner_holds`. It fails when the guard is mutated out.

## 2. tmux detection and viewer

- [x] 2.1 `lib/set_orch/fleet/tmux_view.py`: `pane_of` (environment plus ancestor check), `session_of`,
      `viewer_argv` (the server's own binary, pane-id target). Evidence: tests against a real tmux server,
      including the inherited-environment impostor.
- [x] 2.2 The listing carries `tmux: {pane, viewer}`, and `terminal_label` = viewer label while one is held.
- [x] 2.3 `POST /api/fleet/agents/{pid}/tmux-view`: idempotent, re-derives everything from the pid.
      Evidence: the set-web log line "started tmux viewer tmux-desktape-agent for pid 2250922 (server
      2250921, pane %0 …)", and `tmux list-clients` showed the viewer attached.

## 3. Surface

- [x] 3.1 `terminalOffer` adds a `tmux` kind and `available` with `via: 'tmux'`. The ownership stays
      foreign. Evidence: `web/tests/unit/fleetTerminalTmux.test.ts`.
- [x] 3.2 The tile control opens the viewer, and a refusal stays visible on the control in amber.
- [x] 3.3 The terminal's stop wording for a viewer, and the shown name is the agent's own (`shownLabel`).
- [x] 3.4 idle-close treats a viewer label as unreachable. Evidence: `test_idle_close_does_not_count_a_viewer_as_reachable`.
- [x] 3.5 Visual check in the browser (2026-11-23): the desktape tab showed `desktape-52`, the terminal
      was `live`, and the pending question and the tmux status line were visible.
