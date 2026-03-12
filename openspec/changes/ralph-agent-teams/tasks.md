## 1. State & Config

- [x] 1.1 Add `execution_mode` (default "single") and `parallel_workers` (default 2) fields to `init_loop_state()` in `lib/loop/state.sh`
- [x] 1.2 Add `--parallel` and `--workers N` CLI flags to `bin/wt-loop` start subcommand, pass values to `init_loop_state()`

## 2. Parallel Prompt Template

- [x] 2.1 Create `build_parallel_prompt()` function in `lib/loop/prompt.sh` that generates the parallel subagent instruction block (task partition + worker spawn + review agent)
- [x] 2.2 Modify `build_prompt()` to read `execution_mode` from state file and delegate to `build_parallel_prompt()` when mode is "parallel" and action is `apply:*`
- [x] 2.3 Include spec file paths in the parallel prompt so workers receive relevant specs
- [x] 2.4 Include review agent instructions in the parallel prompt (read-only tools, git diff, gap report format)

## 3. Resume Prompt Awareness

- [x] 3.1 Modify the resume prompt in `engine.sh` to detect `execution_mode=parallel` from state and include parallel continuation instructions

## 4. Orchestrator Integration

- [x] 4.1 Add `execution_mode` and `parallel_workers` to orchestration.yaml schema (global + per-change)
- [x] 4.2 Modify `dispatcher.sh` to read parallel config and pass `--parallel --workers N` to `wt-loop start` when configured

## 5. Testing

- [x] 5.1 Manual test: `wt-loop start "task" --parallel` creates state with `execution_mode=parallel`
- [x] 5.2 Manual test: Run a parallel Ralph iteration on a small change, verify subagents spawn and commit
- [x] 5.3 Manual test: Run without `--parallel`, verify behavior is identical to current (backward compat)
