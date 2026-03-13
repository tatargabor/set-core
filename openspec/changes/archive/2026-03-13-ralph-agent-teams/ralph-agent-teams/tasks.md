# Tasks

## Config & State (ralph-team-config)

- [x] 1.1 Add `--team` flag to `cmd_start()` in `bin/wt-loop` — parse the flag, store in `$team_mode` variable (default: false)
- [x] 1.2 Add `team_mode` field to `init_loop_state()` in `lib/loop/state.sh` — pass the team_mode value and include it in the initial JSON state
- [x] 1.3 Add team metrics fields to `add_iteration()` in `lib/loop/state.sh` — add `team_spawned`, `teammates_count`, `team_tasks_parallel` parameters (default 0/false)
- [x] 1.4 Display team mode in startup banner in `lib/loop/engine.sh` — read `team_mode` from state and show "Team: enabled/disabled" in the banner line

## Prompt Injection (ralph-team-prompt)

- [x] 2.1 Add `build_team_instructions()` function in `lib/loop/prompt.sh` — returns the team instructions text block as a heredoc string
- [x] 2.2 Modify `build_prompt()` in `lib/loop/prompt.sh` — read `team_mode` from loop-state.json, if true call `build_team_instructions()` and append the result to the prompt after openspec_instructions
- [x] 2.3 Write the team instructions content covering: parallelization threshold (3+ independent tasks), teammate spawn configuration (Agent tool, general-purpose, bypassPermissions), commit coordination (only lead commits), task tracking (TaskCreate/TaskUpdate), and teammate cap (max 3)

## Lifecycle Management (ralph-team-lifecycle)

- [x] 3.1 Add cleanup instructions to `build_team_instructions()` — include section on TeamDelete + shutdown_request before iteration exit
- [x] 3.2 Add orphan detection preamble to `build_team_instructions()` — instruct Claude to check for and clean up leftover teams at iteration start

## Metrics Extraction (ralph-team-config)

- [x] 4.1 Add post-iteration team metrics extraction in `lib/loop/engine.sh` — after Claude exits, parse the iteration log file for TeamCreate/Agent tool patterns to extract team_spawned, teammates_count, team_tasks_parallel values
- [x] 4.2 Pass extracted team metrics to `add_iteration()` call in the engine loop
