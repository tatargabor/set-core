# Tasks: unified-orchestration-logging

## Log Path Unification

- [ ] T1: In `bin/set-orchestrate`, change `LOG_FILE=".claude/orchestration.log"` (line 33) to `LOG_FILE="$WT_ORCHESTRATION_LOG"`. Verify `WT_ORCHESTRATION_LOG` is available (set by `set-paths` via `set-common.sh` sourced at line 127).
- [ ] T2: In `bin/set-orchestrate`, remove `LOG_FILE="$_root/$LOG_FILE"` (line 787) — `WT_ORCHESTRATION_LOG` is already an absolute path.
- [ ] T3: In `bin/set-orchestrate`, remove `rotate_log()` function (lines 107-118), `LOG_MAX_SIZE` (line 34), `LOG_KEEP_SIZE` (line 35), and the `rotate_log` call (line 799). Python `RotatingFileHandler` handles rotation.
- [ ] T4: In `bin/set-e2e-report`, change `LOG_FILE=".claude/orchestration.log"` (line 78) to `LOG_FILE="$WT_ORCHESTRATION_LOG"`. Ensure `set-paths` is sourced before this.

## Reference Updates

- [ ] T5: In `lib/set_orch/chat_context.py` (line 138), update `.claude/orchestration.log` reference to use the runtime log path or a generic instruction.

## Verification

- [ ] T6: Verify `set-paths` sources correctly — trace that `WT_ORCHESTRATION_LOG` is set before `log()` is first called in `set-orchestrate`. Check the source chain: `set-common.sh` → `set-paths`.
- [ ] T7: Test standalone `set-orchestrate plan --show` writes log to runtime path, not `.claude/`.
