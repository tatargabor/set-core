## 1. UTF-8 Safe Truncation in wt-hook-memory

- [x] 1.1 ~~Locale fallback~~ Not needed — using bash `${var:0:N}` which is inherently character-safe
- [x] 1.2 Replace `head -c 500` with `${PROMPT:0:500}` on line 583 (emotion save content)
- [x] 1.3 Replace `head -c 200` with `${PROMPT:0:200}` on line 600 (recall query with change name)
- [x] 1.4 Replace `head -c 200` with `${PROMPT:0:200}` on line 602 (recall query without change name)

## 2. Transcript Surrogate Sanitization in _stop_raw_filter

- [x] 2.1 Add a `sanitize_surrogates()` Python helper function inside the `_stop_raw_filter` inline Python block (lines 976-1037) that replaces lone surrogates: `s.encode('utf-8', errors='surrogateescape').decode('utf-8', errors='replace')`
- [x] 2.2 Call `sanitize_surrogates()` on all `content` strings after extraction from `json.loads()` — user content (line 1000), assistant text (line 1012), error content (line 1033)
- [x] 2.3 In the save loop (lines 1072-1079): replace `except Exception: pass` with `except UnicodeEncodeError as e: print(f'UnicodeEncodeError at entry {i}: {e}', file=sys.stderr)` followed by `except Exception as e: print(f'Error at entry {i}: {e}', file=sys.stderr)`, both with `continue`

## 3. Defense-in-Depth in wt-memory cmd_remember

- [x] 3.1 In `bin/wt-memory` cmd_remember inline Python (line ~445-455), add content sanitization before `m.remember()`: `content = os.environ['_SHODH_CONTENT']; content = content.encode('utf-8', errors='replace').decode('utf-8')`

## 4. Stop Hook Extraction Content Safety

- [x] 4.1 In `_stop_migrate_staged()` (line 1139): pipe content through `iconv -c -t utf-8` before `wt-memory remember`, or use bash `${content}` with a sanitization step
- [x] 4.2 In `_stop_commit_extraction()` codemap save (line 1238): ensure `codemap_content` truncation uses `${var:0:N}` (already does — verified character-safe in bash)
- [x] 4.3 In `_stop_commit_extraction()` design choices save (line 1261): same verification — confirmed `${content:0:297}` is character-safe

## 5. RocksDB LOG.old Cleanup

- [x] 5.1 Add `cmd_cleanup_logs()` function to `bin/wt-memory`: find and delete `LOG.old.*` files older than 24 hours in `$storage_path/memories/` and `$storage_path/memory_index/`, report count and bytes reclaimed
- [x] 5.2 Register `cleanup-logs` in the wt-memory CLI dispatch
- [x] 5.3 In `wt-hook-memory` Stop handler (`handle_stop()`), call `wt-memory cleanup-logs` before `_stop_run_extraction_bg`, with `|| true` to not block on failure

## 6. CLAUDE.md Citation Enforcement

- [x] 6.1 Update the `Persistent Memory` section template in `bin/wt-project` to use a numbered action list: (1) Scan system-reminder tags, (2) Match against user's question, (3) Cite with "From memory: ...", (4) Only then proceed with independent research
- [x] 6.2 Run `wt-project init` on target projects to deploy the updated CLAUDE.md section
- [x] 6.3 Update this project's CLAUDE.md with the same strengthened instruction

## 7. Validation and Cleanup

- [x] 7.1 Run `wt-memory cleanup-logs` on a test project — reclaimed significant LOG.old space (24h threshold for ongoing)
- [x] 7.2 Test: bash `${var:0:N}` is character-safe — `head -c` and `cut -c` are NOT (GNU coreutils byte-level). Verified multi-byte char at boundary: valid UTF-8.
- [x] 7.3 Test: `_stop_raw_filter` on a real transcript — entries extracted without crash, sanitize_surrogates() applied
- [x] 7.4 Verify: saved test memory with non-ASCII text including all Hungarian accented chars — stored and recalled correctly.
