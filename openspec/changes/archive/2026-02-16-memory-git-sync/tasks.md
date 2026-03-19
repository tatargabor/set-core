## 1. Sync Infrastructure

- [x] 1.1 Add `sync_resolve_identity()` helper: derive `<user>/<machine>` from `git config user.name` + `hostname -s` (lowercase, sanitize)
- [x] 1.2 Add `.sync-state` read/write helpers: `sync_read_state()` and `sync_write_state()` operating on `<storage_path>/.sync-state` JSON
- [x] 1.3 Add `sync_export_hash()` helper: run `set-memory export` and return sha256 of the output

## 2. Push Command

- [x] 2.1 Implement `cmd_sync_push`: export → hash check → skip if unchanged → temp dir clone/init → write file → commit → push → update `.sync-state` → cleanup
- [x] 2.2 Handle first push: create orphan branch when `set-memory` branch doesn't exist on remote
- [x] 2.3 Handle subsequent push: clone existing branch with `--depth 1`, update file, commit, push

## 3. Pull Command

- [x] 3.1 Implement `cmd_sync_pull`: fetch → commit hash check → skip if unchanged → list remote files → extract foreign files via `git show` → import each → update `.sync-state`
- [x] 3.2 Add `--from <user/machine>` flag for selective pull
- [x] 3.3 Print per-source import summary (e.g., "alice/workstation: 12 new, 45 skipped")

## 4. Sync and Status Commands

- [x] 4.1 Implement `cmd_sync` (no subcommand): call push then pull in sequence
- [x] 4.2 Implement `cmd_sync_status`: show last push/pull timestamps + list remote `<user>/<machine>` entries

## 5. CLI Integration

- [x] 5.1 Add `sync` to the `case` dispatch in `main()` with sub-dispatch for push/pull/status
- [x] 5.2 Update `usage()` with Sync section listing all sync subcommands
- [x] 5.3 Add graceful degradation checks: not a git repo, no remote, shodh-memory not installed

## 6. Testing

- [x] 6.1 Write tests for sync identity resolution (user/machine sanitization)
- [x] 6.2 Write tests for push: first push (orphan creation), subsequent push, skip when unchanged
- [x] 6.3 Write tests for pull: import from others, skip when unchanged, selective pull with `--from`
- [x] 6.4 Write tests for sync status output
- [x] 6.5 Write tests for graceful degradation (no remote, not git repo)
