## 1. Update memory.md (major rewrite)

- [x] 1.1 Rewrite subcommand list to match all CLI categories: Core, Forget/Cleanup, Diagnostics, Introspection, Export/Import, Sync, Maintenance
- [x] 1.2 Fix memory types: replace `Observation, Event` with `Decision, Learning, Context` and note legacy aliases
- [x] 1.3 Add recall modes documentation (semantic, temporal, hybrid, causal, associative)
- [x] 1.4 Update execution instructions for new subcommands (passthrough pattern for forget, stats, cleanup, get, context, brain, export, import, sync status, migrate, repair)

## 2. Update loop.md

- [x] 2.1 Add missing start flags: `--stall-threshold`, `--iteration-timeout`, `--permission-mode`, `--label`, `--force`
- [x] 2.2 Add `--done openspec` option (auto-detects openspec alongside tasks/manual)

## 3. Update merge.md

- [x] 3.1 Fix `--target` to `--to` and add `--squash`, `--no-push` flags

## 4. Update work.md

- [x] 4.1 Add `-e/--editor`, `--no-create`, `-p/--project` flags and document multi-editor support

## 5. Update new.md

- [x] 5.1 Add `-b/--branch`, `--skip-fetch`, `--new`, `-p/--project` flags

## 6. Deploy updated skills

- [x] 6.1 Run `set-project init` in set-core repo to deploy updated command files
