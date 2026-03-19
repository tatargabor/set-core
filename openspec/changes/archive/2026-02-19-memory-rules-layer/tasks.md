## 1. Rules File & CLI

- [x] 1.1 Add `rules` subcommand dispatcher to `bin/set-memory` (routes `add`, `list`, `remove`)
- [x] 1.2 Implement `set-memory rules add --topics "t1,t2" "content"` — auto-generates kebab-case id, appends to `.claude/rules.yaml`
- [x] 1.3 Implement `set-memory rules list` — prints id, topics, content preview for all rules
- [x] 1.4 Implement `set-memory rules remove <id>` — removes matching entry, errors if not found
- [x] 1.5 Resolve project root for rules file via `git rev-parse --show-toplevel`, fallback to `$CLAUDE_PROJECT_DIR`

## 2. Hook Injection

- [x] 2.1 Add `load_matching_rules()` helper in `bin/wt-hook-memory` — reads `.claude/rules.yaml`, matches topics against prompt text (bash, case-insensitive), silently skips if file missing or malformed
- [x] 2.2 Extend `handle_user_prompt()` to call `load_matching_rules()` and prepend `=== MANDATORY RULES ===` block before project memory in `additionalContext` output when rules match
- [x] 2.3 Add debug logging for rules injection (rule count, matched ids) to `/tmp/wt-hook-memory.log`

## 3. Cheat-Sheet Scope Clarification

- [x] 3.1 Update L5 haiku extraction prompt in `bin/wt-hook-memory` — add explicit instruction to NOT promote credential-like or hard-constraint content to cheat-sheet; those belong in rules
- [x] 3.2 Update `docs/developer-memory.md` — add Rules section (file format, CLI usage, when to use rules vs cheat-sheet), update cheat-sheet section with scope guidance

## 4. Tests

- [x] 4.1 Add CLI tests for `set-memory rules add` / `list` / `remove` (in `tests/` or `tests/cli/`)
- [x] 4.2 Add hook injection test: mock `.claude/rules.yaml` with a topic, fire UserPromptSubmit hook, assert `MANDATORY RULES` section appears in output
- [x] 4.3 Add hook graceful-degrade test: missing rules file → no rules section, hook exits 0
- [x] 4.4 Add hook graceful-degrade test: malformed YAML → no rules section, hook exits 0
