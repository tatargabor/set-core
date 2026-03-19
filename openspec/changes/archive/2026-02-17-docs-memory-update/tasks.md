## 1. Screenshot

- [x] 1.1 Save user-provided screenshot as `docs/images/control-center-memory.png`
- [x] 1.2 Add screenshot reference in `docs/developer-memory.md` under `## GUI` heading with caption describing M/O/R badges

## 2. CLI Reference — developer-memory.md

- [x] 2.1 Add `set-memory audit [--threshold N] [--json]` to CLI Reference table in `docs/developer-memory.md` (Diagnostics section, alongside existing `repair`)
- [x] 2.2 Add `set-memory dedup [--threshold N] [--dry-run] [--interactive]` to CLI Reference table in `docs/developer-memory.md`

## 3. CLI Reference — README.md

- [x] 3.1 Add `set-memory audit` row to Developer Memory CLI table in `README.md`
- [x] 3.2 Add `set-memory dedup` row to Developer Memory CLI table in `README.md`

## 4. CLI Reference — readme-guide.md

- [x] 4.1 Add `set-memory audit` and `set-memory dedup` to the mandatory Developer Memory CLI list in `docs/readme-guide.md`

## 5. Happy-Flow Setup Guides

- [x] 5.1 Add `### Quick Setup Flows` subsection after existing step 3 in `docs/developer-memory.md` Setup section
- [x] 5.2 Write Flow A: Fresh project init (pip install shodh-memory → set-project init → wt-openspec init → set-memory-hooks install → set-memory-hooks check)
- [x] 5.3 Write Flow B: Add memory to existing OpenSpec project (pip install shodh-memory → set-project init (re-run) → set-memory-hooks install → set-memory-hooks check)
- [x] 5.4 Write Flow C: After OpenSpec update (wt-openspec update → set-memory-hooks install → set-memory-hooks check)

## 6. Staging Pattern Documentation

- [x] 6.1 Extend `wt-hook-memory-save` description in automatic hooks section of `docs/developer-memory.md` to document staging+debounce pattern (staging files, commit-on-switch, 5-min debounce)

## 7. Comparison with Claude Code Memory

- [x] 7.1 Add `## How set-memory Differs from Claude Code Memory` section in `docs/developer-memory.md` after Quick Start
- [x] 7.2 Write framing paragraph: complementary not competing — CLAUDE.md = instructions, set-memory = experience
- [x] 7.3 Add comparison table: storage, recall method, structure, scale, worktree behavior, team sharing, lifecycle
- [x] 7.4 Highlight worktree sharing difference: Claude auto memory isolates worktrees, set-memory shares across same-repo worktrees

## 8. set-project init Documentation

- [x] 8.1 Update `set-project init` description in README Quick Start to mention it deploys hooks+commands+skills (not just registers)
- [x] 8.2 Update `set-project` description in README CLI Reference (Worktree Management table) to reflect deploy behavior
