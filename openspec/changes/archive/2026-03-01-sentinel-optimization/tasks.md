# Tasks

## Poll Loop Rewrite

- [x] 1.1 Rewrite Step 2 in `.claude/commands/wt/sentinel.md` — replace the bash while-loop with a single-shot poll command that uses `run_in_background: true`. The command: `sleep 30`, read `orchestration-state.json`, check PID liveness, check terminal/checkpoint/stale states, output a single `EVENT:type|key=value` line.

- [x] 1.2 Rewrite Step 3 decision tree — add explicit handling for `EVENT:running` that simply starts the next background poll with minimal output (no analysis). Keep existing decision logic for other events (terminal, process_exit, checkpoint, stale).

- [x] 1.3 Add instruction for the LLM to loop: after handling any non-terminal event, restart the background poll (go to Step 2). Make the flow explicit: "After handling the event, if the orchestrator is still running, go back to Step 2."

## Responsiveness

- [x] 2.1 Add a note in the skill prompt that the user can interact between polls — the sentinel should respond to user questions about orchestration status by reading `orchestration-state.json` directly (not waiting for the next poll).

## Deploy

- [x] 3.1 Run `set-project init` to deploy updated sentinel skill to all registered projects.
