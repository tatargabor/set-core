## Tasks

### Group 1: set-memory-hooks CLI

- [x] 1.1 Create `bin/set-memory-hooks` with `resolve_main_repo()` (reuse pattern from `wt-openspec`)
- [x] 1.2 Implement `check` command: scan `.claude/skills/openspec-*/SKILL.md` for marker comments, output JSON `{"installed": bool, "files_total": N, "files_patched": N}`
- [x] 1.3 Define hook templates as heredocs for all 5 skills (new-change 1b, continue-change 2b, ff-change 3b, apply-change 4b+7 extension, archive-change 7)
- [x] 1.4 Implement `install` command: for each target SKILL.md, skip if markers present, otherwise find anchor line and insert hook block with markers
- [x] 1.5 Implement `remove` command: delete lines between markers (inclusive) from all SKILL.md files
- [x] 1.6 Add `set-memory-hooks` to `install.sh` scripts array

### Group 2: /wt:memory slash command

- [x] 2.1 Create `.claude/commands/wt/memory.md` with subcommand routing (status, list, recall, remember, browse)
- [x] 2.2 Define `status` subcommand: run `set-memory status`, display result
- [x] 2.3 Define `recall` subcommand: run `set-memory recall "<query>" --limit 5`, display results
- [x] 2.4 Define `remember` subcommand: prompt for type and tags, run `echo "<content>" | set-memory remember --type <type> --tags <tags>`
- [x] 2.5 Define `list`/`browse` subcommand: run `set-memory list`, display grouped by type

### Group 3: GUI — Memory submenu hooks action

- [x] 3.1 Add hook status to FeatureWorker poll: run `set-memory-hooks check --json`, merge into `_feature_cache[project]["memory"]`
- [x] 3.2 Update Memory submenu in `menus.py`: show "Install Memory Hooks" when openspec detected and hooks not installed, or disabled "Memory Hooks: installed" when installed
- [x] 3.3 Implement `_run_memory_hooks_install` in `menus.py`: run `set-memory-hooks install` via CommandOutputDialog, refresh cache
- [x] 3.4 Update [M] button tooltip in `table.py`: append "(hooks installed)" or "(hooks not installed)" when openspec is present

### Group 4: Auto-reinstall after OpenSpec update

- [x] 4.1 Modify `_run_openspec_action` in `menus.py`: after `wt-openspec update` succeeds, check if hooks were installed before, if yes run `set-memory-hooks install` automatically
- [x] 4.2 Show both operations in CommandOutputDialog output (update + hook reinstall)

### Group 5: Tests

- [x] 5.1 Test `set-memory-hooks check` output format (mock SKILL.md files with/without markers)
- [x] 5.2 Update `test_29_memory.py`: test hooks status in [M] tooltip, test "Install Memory Hooks" menu action
- [x] 5.3 Update `test_30_openspec_button.py`: test auto-reinstall behavior in feature cache
