## Why

During development conversations, ideas and future directions pop up that shouldn't be pursued immediately but shouldn't be lost either. Currently there's no quick way to capture these — `/wt:memory remember` asks questions (type? tags?), breaking flow. We need a fire-and-forget `/wt:todo` skill that saves an idea to memory in one shot and lets the agent continue with current work.

## What Changes

- **New `/wt:todo` slash command**: Saves a todo/idea to shodh-memory with auto-tags (`todo`, `backlog`, current change name). No questions asked — just save and confirm.
- **List subcommand**: `/wt:todo list` retrieves all open todos using `--tags-only --tags todo`.
- **Done subcommand**: `/wt:todo done <id>` removes a completed todo from memory.

## Capabilities

### New Capabilities
- `memory-todo`: The `/wt:todo` slash command for quick idea capture, listing, and completion

### Modified Capabilities

## Impact

- **`.claude/commands/wt/todo.md`**: New slash command definition
- **No code changes to `bin/wt-memory`**: Uses existing CLI commands (`remember`, `recall --tags-only`, `forget`)
- **No breaking changes**: Purely additive
