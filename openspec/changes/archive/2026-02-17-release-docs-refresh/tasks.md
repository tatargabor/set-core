## 1. Code change: Team Sync default

- [x] 1.1 Change `team.sync_interval_ms` default from 15000 → 120000 in `gui/constants.py:244`

## 2. readme-guide.md updates

- [x] 2.1 Add `wt-openspec` to user-facing commands list in CLI Documentation Rules
- [x] 2.2 Add `wt-hook-memory-recall`, `wt-hook-memory-save` to internal/hook scripts list
- [x] 2.3 Add `set-memory sync`, `set-memory proactive`, `set-memory stats`, `set-memory cleanup`, `set-memory-hooks remove` to Developer Memory CLI must-include list

## 3. README.md full refresh

- [x] 3.1 Update "Latest update" date to 2026-02-17
- [x] 3.2 Add missing Developer Memory CLI commands to CLI Reference table: sync (push/pull/status), proactive, stats, cleanup
- [x] 3.3 Add `set-memory-hooks remove` to CLI Reference table
- [x] 3.4 Add `wt-openspec init`, `wt-openspec status`, `wt-openspec update` to CLI Reference (new OpenSpec category or under Project Management)
- [x] 3.5 Add `wt-hook-memory-recall` and `wt-hook-memory-save` to internal hooks note
- [x] 3.6 Expand Developer Memory Features section: GUI memory ([M] button, Browse dialog summary/list modes, semantic search, Remember Note, Export/Import)
- [x] 3.7 Add Team Sync traffic warning: note that `wt-control-sync` generates git fetch+push per cycle, recommend 2-minute default, document how to change in Settings
- [x] 3.8 Add memory recall modes (semantic, temporal, hybrid, causal, associative) to Developer Memory section or link to docs/developer-memory.md
- [x] 3.9 Verify all 16 mandatory sections present and in order per readme-guide.md
- [x] 3.10 Verify code examples are copy-pasteable

## 4. Supporting docs cleanup

- [x] 4.1 Update `docs/config.md` section count from 14 → 16 matching current mandatory sections
- [x] 4.2 Remove empty `AGENTS.md` (0 bytes, no purpose)

## 5. Verification

- [x] 5.1 Run `ls bin/wt-*` and cross-check every command is either in CLI Reference or internal hooks note
- [x] 5.2 Run through readme-guide.md Update Checklist (all 8 items)
