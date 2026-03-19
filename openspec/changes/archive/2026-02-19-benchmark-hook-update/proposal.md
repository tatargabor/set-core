## Why

The benchmark init scripts and CLAUDE.md templates are outdated — they reference `set-memory-hooks` (deprecated, not in PATH) and use the old "Proactive Memory" pattern with manual `set-memory recall/remember` instructions. The hook-driven memory system (`wt-deploy-hooks` + `wt-hook-memory`) now handles recall/save automatically, but the benchmark doesn't use it. This means benchmark runs don't test the actual memory system as deployed.

## What Changes

- Remove `set-memory-hooks install` from `init-with-memory.sh` (deprecated, binary doesn't exist)
- Remove `set-memory-hooks` prerequisite check from `init-with-memory.sh`
- Replace "Proactive Memory" section in `benchmark/claude-md/with-memory.md` with the "Persistent Memory" section from the main CLAUDE.md (hook-driven, cite-from-memory instructions)
- Update `run-guide.md` to remove references to `set-memory-hooks`

## Capabilities

### New Capabilities

### Modified Capabilities
- `smart-memory-recall`: The benchmark CLAUDE.md now relies on hook-driven recall instead of manual recall instructions

## Impact

- `benchmark/init-with-memory.sh` — remove deprecated set-memory-hooks usage
- `benchmark/claude-md/with-memory.md` — replace Proactive Memory with Persistent Memory
- `benchmark/run-guide.md` — remove set-memory-hooks references
- No code changes to bin/ scripts
