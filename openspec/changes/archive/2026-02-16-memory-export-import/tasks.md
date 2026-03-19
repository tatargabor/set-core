## 1. CLI Export

- [x] 1.1 Add `cmd_export` function to `bin/set-memory` — list all memories, build JSON with version header, output to stdout
- [x] 1.2 Add `--output <path>` flag to write export JSON to file instead of stdout
- [x] 1.3 Handle empty project (valid JSON with count: 0, empty records)
- [x] 1.4 Wire `export` command in main dispatch case statement and update usage text

## 2. CLI Import

- [x] 2.1 Add `cmd_import` function to `bin/set-memory` — read JSON file, validate format/version
- [x] 2.2 Implement dedup logic: build known-ID set from existing records (id + metadata.original_id), skip matches
- [x] 2.3 Import non-duplicate records via `remember()` with original content, type, tags, entities, and metadata.original_id
- [x] 2.4 Add `--dry-run` flag that reports would_import/would_skip without writing
- [x] 2.5 Output JSON result (`imported`, `skipped`, `errors` or dry-run equivalent)
- [x] 2.6 Handle error cases: invalid JSON, unknown version, missing format field, file not found
- [x] 2.7 Wire `import` command in main dispatch and update usage text

## 3. CLI Tests

- [x] 3.1 Create `tests/test_memory_export_import.py` with isolated SHODH_STORAGE fixture
- [x] 3.2 Test export full project — valid JSON schema, all fields present
- [x] 3.3 Test export empty project — valid JSON, count 0
- [x] 3.4 Test import into empty project — all records imported, original_id set in metadata
- [x] 3.5 Test dedup: skip by exact ID match
- [x] 3.6 Test dedup: skip by original_id match in target
- [x] 3.7 Test dedup: skip reverse import (incoming original_id matches target id)
- [x] 3.8 Test dedup: skip double-import (incoming original_id matches target original_id)
- [x] 3.9 Test full roundtrip A→B→A — no duplicates after roundtrip
- [x] 3.10 Test import mixed (some new, some duplicate) — correct counts
- [x] 3.11 Test dry-run — no writes, correct preview counts
- [x] 3.12 Test invalid file handling (bad JSON, wrong version, missing format)

## 4. GUI Export/Import Buttons

- [x] 4.1 Add Export button to Memory Browse Dialog top bar (after Show All/Summary toggle)
- [x] 4.2 Implement `_on_export` handler: directory picker, auto-named file, call `set-memory export --output`, success/warning dialog
- [x] 4.3 Add Import button to Memory Browse Dialog top bar
- [x] 4.4 Implement `_on_import` handler: file picker (JSON filter), call `set-memory import`, result dialog with counts, refresh list
- [x] 4.5 Handle edge cases: no memories to export, invalid file on import, set-memory not available

## 5. GUI Tests

- [x] 5.1 Add export/import button existence tests to `tests/gui/test_29_memory.py`
- [x] 5.2 Test export button triggers directory picker (mock _run_wt_memory and get_existing_directory)
- [x] 5.3 Test import button triggers file picker and shows result dialog (mock _run_wt_memory and get_open_filename)

## 6. Documentation

- [x] 6.1 Update `docs/readme-guide.md` CLI coverage matrix with export/import commands
- [x] 6.2 Update `README.md` with export/import usage examples
