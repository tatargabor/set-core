"""Regression test: orchestration-dispatched changes get 90m per iteration.

Observed on craftbrew-run-20260415-0146 admin-products: fix agent was
iterating through Playwright strategies for the Radix Select click-hang
(force, evaluate, mouse.click at coords, reload, keyboard-only). Each
strategy costs ~8 min (edit → playwright run → analyze). The agent was
converging on keyboard-first — the right answer — at minute 40+ when
set-loop's default iteration timeout (45 min via the `timeout --signal=TERM`
wrapper) SIGTERM'd claude mid-solution.

set-loop CLI default (45) is fine for quick implementations but tight for
framework-integration fix cycles under --verify dispatch. dispatch_via_wt_loop
now passes --iteration-timeout 90 explicitly. Manual set-loop users keep
the 45-min default.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))


def test_dispatch_via_wt_loop_passes_90min_iteration_timeout(tmp_path):
    from set_orch import dispatcher

    loop_state = tmp_path / ".set" / "loop-state.json"
    loop_state.parent.mkdir(parents=True)
    loop_state.write_text('{"terminal_pid": 123456}')

    state_file = tmp_path / "state.json"
    state_file.write_text('{"status":"running","changes":[{"name":"x","extras":{}}]}')

    captured_cmd: list[list[str]] = []

    def fake_run(cmd, cwd=None, timeout=None):
        captured_cmd.append(cmd)
        r = MagicMock()
        r.exit_code = 0
        r.stdout = ""
        r.stderr = ""
        return r

    with patch.object(dispatcher, "run_command", side_effect=fake_run), \
         patch.object(dispatcher, "_kill_existing_wt_loop"), \
         patch.object(dispatcher, "send_notification"), \
         patch.object(dispatcher, "update_change_field"):
        dispatcher.dispatch_via_wt_loop(
            state_path=str(state_file),
            change_name="x",
            impl_model="claude-opus-4-6",
            wt_path=str(tmp_path),
            scope="test scope",
        )

    assert captured_cmd, "set-loop command was never constructed"
    cmd = captured_cmd[0]
    # --iteration-timeout must appear with value 90 (not the set-loop CLI
    # default 45, which is too short for framework-integration fix cycles).
    assert "--iteration-timeout" in cmd, (
        f"dispatch_via_wt_loop must pass --iteration-timeout explicitly; got {cmd!r}"
    )
    idx = cmd.index("--iteration-timeout")
    assert cmd[idx + 1] == "90", (
        f"--iteration-timeout must be 90 minutes (framework fix cycles), got {cmd[idx + 1]!r}"
    )
