## Why

Projects with non-ASCII content (Hungarian, emoji, CJK, etc.) lose memories silently. The transcript extraction pipeline crashes on UTF-8 surrogate characters created by byte-level truncation (`head -c N`) splitting multi-byte sequences. Additionally, RocksDB accumulates hundreds of MB in LOG.old files across projects, and the memory citation rate is near-zero — agents receive injected memories but almost never explicitly use them.

## What Changes

- **Fix UTF-8 surrogate corruption in `wt-hook-memory`**: Replace `head -c N` byte-level truncation (lines 583, 600, 602) with character-safe truncation that cannot split multi-byte UTF-8 sequences. This is the primary source of `UnicodeEncodeError: surrogates not allowed` errors.
- **Fix surrogate propagation in `_stop_raw_filter()`**: Sanitize lone surrogates from Node.js JSONL transcripts (which can contain unpaired surrogate escapes) before passing content to `wt-memory remember`. Currently the `except Exception: pass` on line 1078 silently drops entries with surrogates.
- **Add UTF-8 sanitization in `wt-memory cmd_remember`**: Defense-in-depth — sanitize content in the Python layer before passing to the Rust/PyO3 `m.remember()` call, so no surrogate can ever reach RocksDB.
- **RocksDB LOG.old cleanup**: Add periodic cleanup of LOG.old files and document the upstream fix needed in shodh-memory (`keep_log_file_num` config exposure).
- **Strengthen CLAUDE.md memory citation instructions**: Make the memory citation directive more explicit and harder to ignore, so agents actually use injected memories.
- **Investigate haiku transcript extraction cost**: The post-session extraction uses haiku for cheap extraction — verify it's actually running and not wasting tokens on empty/failed extractions.

## Capabilities

### New Capabilities
- `utf8-safe-content-handling`: Ensure all text flowing through the hook pipeline and into wt-memory is valid UTF-8, with character-safe truncation and surrogate sanitization at every boundary.
- `rocksdb-log-cleanup`: Periodic cleanup of RocksDB LOG.old file accumulation, with documentation for upstream shodh-memory fix.

### Modified Capabilities
- `hook-driven-memory`: Fix `head -c` byte truncation in UserPromptSubmit handler (line 583) and recall query construction (lines 600, 602).
- `raw-transcript-filter`: Fix surrogate propagation in `_stop_raw_filter()` — sanitize content after `json.loads()` and replace silent `except Exception: pass` with proper error logging.
- `stop-hook-extraction`: Fix the commit extraction path (lines 1139, 1238, 1261) to sanitize content before `wt-memory remember`.
- `ambient-memory`: Strengthen CLAUDE.md citation instructions to increase the near-zero citation rate.

## Impact

- **`bin/wt-hook-memory`**: Primary fix target — UTF-8 truncation and surrogate sanitization across ~6 code locations.
- **`bin/wt-memory`**: Defense-in-depth sanitization in `cmd_remember` Python inline script (line ~438).
- **CLAUDE.md template** (used by `wt-project init`): Stronger memory citation instructions.
- **All projects using memory hooks**: The UTF-8 fix benefits any project with non-ASCII content (Hungarian, emoji, CJK, etc.).
- **Disk usage**: Periodic cleanup prevents LOG.old re-accumulation across all projects.
