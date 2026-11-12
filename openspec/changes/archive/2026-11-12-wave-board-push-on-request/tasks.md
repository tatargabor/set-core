## 1. Hook

- [x] 1.1 `bin/set-hook-waveboard`: exit 0 silently unless `SET_WAVEBOARD_PUSH` is on/1/true/yes/worktree; docstring states the opt-in and the reason

## 2. Skill

- [x] 2.1 `.claude/skills/set/wave-board/SKILL.md`: the board's default target is the job file; push and review only on request or with `SET_WAVEBOARD_PUSH=on`; the end-of-session `pending` step only then

## 3. Tests

- [x] 3.1 `tests/unit/test_wave_board.py`: the `hook()` helper opts in; new test: unset → silent and sync not run (no `.set/waveboard/` state written); `off` and garbage values silent. Live: the installed hook printed nothing in a real repo with `docs/waveboard/`, in 40 ms
- [x] 3.2 Mutation check: with the old default restored, 3 of the 4 new cases fail (unset, empty, garbage; `off` was silent before too)
- [x] 3.3 `tests/unit/test_wave_board.py` + `tests/unit/test_fleet_waveboards.py`: 102 passed
