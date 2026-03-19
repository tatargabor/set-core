# Tasks: shodh-memory-integration

## 1. Create `bin/set-memory` bash helper

- [x] Create `bin/set-memory` with `health`, `remember`, `recall`, `status` commands
- [x] Implement graceful degradation: health check before every operation, silent no-op on failure
- [x] Support `SHODH_HOST`, `SHODH_PORT`, `SHODH_API_KEY` environment variables (defaults: 127.0.0.1:3030)
- [x] Remember: read content from stdin, POST to `/api/remember` with `--type` and `--tags`
- [x] Recall: POST query to `/api/recall`, output JSON to stdout, return `[]` on failure
- [x] Make script executable (`chmod +x`)

## 2. Modify SKILL.md files

- [x] `openspec-archive-change/SKILL.md`: Add Step 7 — save decisions, learnings, and completion event to memory after archive
- [x] `openspec-continue-change/SKILL.md`: Add Step 2b — recall relevant past experience before acting on status
- [x] `openspec-ff-change/SKILL.md`: Add Step 3b — recall past experience before artifact creation loop
- [x] `openspec-apply-change/SKILL.md`: Add Step 4b — recall patterns and errors before implementing
- [x] `openspec-apply-change/SKILL.md`: Extend Step 7 — remember errors, patterns, and completion events after implementation
- [x] `openspec-new-change/SKILL.md`: Add Step 1b — check for related past work after getting user description

## 3. Update install.sh

- [x] Add `set-memory` to the `scripts` array in `install_scripts()` function

## 4. Verify graceful degradation

- [x] `set-memory health` exits 1 when shodh-memory is not running
- [x] `echo "test" | set-memory remember --type Learning` exits 0 silently (no-op)
- [x] `set-memory recall "test"` outputs `[]` and exits 0
- [x] `set-memory status` shows config and "not reachable" message
