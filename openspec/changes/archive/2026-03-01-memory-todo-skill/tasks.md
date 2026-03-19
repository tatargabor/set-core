## 1. Create the slash command

- [ ] 1.1 Create `.claude/commands/wt/todo.md` with save/list/done subcommand routing
- [ ] 1.2 Implement save logic: parse text from arguments, health check, auto-detect change, call `set-memory remember`
- [ ] 1.3 Implement list logic: call `set-memory recall --tags-only --tags todo`, format output with IDs
- [ ] 1.4 Implement done logic: call `set-memory forget <id>`, confirm deletion
- [ ] 1.5 Add explicit "do not pursue" instruction to prevent agent from acting on todo content
- [ ] 1.6 Handle edge case: no arguments → ask user what to save
