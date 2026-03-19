## 1. Loop State — store test_command

- [x] 1.1 Add `test_command: Optional[str] = None` field to `LoopState` dataclass in `lib/set_orch/loop_state.py` (after `ff_max_retries` at line 50)
- [x] 1.2 Verify `to_dict()` / `from_dict()` round-trips the new field — note: `dataclasses.asdict()` emits `None` fields as `"test_command": null`, treat `None` as absent in `_check_test_done()`

## 2. wt-loop CLI — accept --test-command flag

- [x] 2.1 Declare `local test_command=""` in `cmd_start()` alongside other local variables (lines 110-124 in `bin/wt-loop`)
- [x] 2.2 Add `--test-command` case to argument parsing (after the `--done` case around line 128)
- [x] 2.3 Pass `test_command` value to `loop-state.json` when writing initial state
- [x] 2.4 Update help text (line 59) to document `--test-command <cmd>` and add `test` to the `--done` accepted values list

## 3. Core — implement _check_test_done()

- [x] 3.1 Add `_check_test_done(wt_path: str) -> bool` function in `lib/set_orch/loop_tasks.py` (near `_check_build_done` at line 243)
- [x] 3.2 Implement fallback chain: (1) read `test_command` from `loop-state.json` at `os.path.join(wt_path, ".claude", "loop-state.json")` — treat `None` as absent, (2) `config.auto_detect_test_command(wt_path)`, (3) `_check_build_done(wt_path)`
- [x] 3.3 Execute test command via `subprocess.run(cmd, shell=True, cwd=wt_path, capture_output=True, text=True, timeout=300)` — return `returncode == 0`
- [x] 3.4 Wire into `is_done()` at line 155: add `elif done_criteria == "test": return _check_test_done(wt_path)` before the final `return False`

## 4. Orchestrator — resume_change passes test command

- [x] 4.1 In `resume_change()` (`lib/set_orch/dispatcher.py:1153`), resolve test command from directives state extras, then `config.auto_detect_test_command(wt_path)` as fallback
- [x] 4.2 Append `--test-command <cmd>` to the `wt-loop start` command list (around line 1233) when test command is non-empty

## 5. Unit Tests

- [x] 5.1 Test `_check_test_done()` — mock subprocess, verify True on exit 0, False on non-zero, False on timeout
- [x] 5.2 Test `_check_test_done()` fallback chain — no loop-state test_command → auto-detect → build fallback
- [x] 5.3 Test `is_done("test")` dispatches to `_check_test_done()`
- [x] 5.4 Test `LoopState` serialization round-trip with `test_command` field
- [x] 5.5 Test `resume_change()` includes `--test-command` in wt-loop command when test command available
- [x] 5.6 Test that existing stopped→failed mapping covers `done_criteria="test"` case
