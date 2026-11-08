## 1. Implementation

- [x] 1.1 `push_marks` / `push_class` in `bin/set-wave-board`; `sync` reports `push_class`, `pushed_at`, `combined_push_class`, `combined_pushed_at`
- [x] 1.2 `pushed` stores the marks when the recorded hash is the payload's own
- [x] 1.3 `set-hook-waveboard`: per-job decision (`due_pushes`), `SET_WAVEBOARD_DEBOUNCE_SECONDS`, the reason names why it asks and says to push both targets in one go
- [x] 1.4 Skill: the class table and the end-of-session / handoff flush

## 2. Verification

- [x] 2.1 Tests: marks recorded; foreign hash → no marks → `progress`; first at once; progress waits for the debounce; blocked and a finished wave are milestones; notes never asked and still pending; board + combined one block, one clock — `tests/unit/test_wave_board.py` + `test_fleet_waveboards.py`: 98 passed
- [x] 2.2 Mutations caught: notes→progress, milestone→progress, notes-skip removed, debounce replaced by the nag backoff. The per-target nag key mutation survives as an equivalent mutant (the decision reads the job's stamp)
