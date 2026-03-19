## Context

Projects with non-ASCII content (Hungarian, emoji, CJK) lose memories silently. Investigation revealed three root causes:

1. **UTF-8 surrogate corruption**: `head -c N` in `wt-hook-memory` truncates at byte boundaries, splitting multi-byte UTF-8 sequences (Hungarian accented characters: á=0xc3 0xa1, é=0xc3 0xa9, etc.). The orphaned lead byte (e.g., 0xc3) passes through bash variables, gets decoded by Python's `os.environ` with `surrogateescape` error handler, producing `\udcc3`. The Rust/PyO3 `m.remember()` rejects this as invalid UTF-8.

2. **Silent error swallowing**: In `_stop_raw_filter()`, the `except Exception: pass` on line 1078 silently drops entries that fail `subprocess.run(..., text=True)` — which also fails on surrogate content. Additionally, Node.js JSONL transcripts can contain unpaired surrogate escapes from `JSON.stringify`, which `json.loads()` faithfully decodes into Python surrogate codepoints.

3. **RocksDB LOG.old accumulation**: Each `set-memory` CLI call opens/closes RocksDB, creating a LOG.old file. Over many sessions, thousands of LOG.old files accumulate (tens of MB wasted per project).

Secondary issue: Memory citation rate is near-zero across projects. The CLAUDE.md instruction exists but agents don't follow it consistently.

## Goals / Non-Goals

**Goals:**
- Fix UTF-8 handling so all non-ASCII content (Hungarian, emoji, CJK) flows safely through the entire pipeline
- Add defense-in-depth sanitization at the `set-memory remember` boundary
- Replace silent error swallowing with logged errors in transcript extraction
- Provide RocksDB LOG.old cleanup mechanism
- Strengthen CLAUDE.md citation instruction to increase actual usage

**Non-Goals:**
- Modifying shodh-memory Rust source (upstream change — document only)
- Changing the memory extraction strategy (raw filter vs LLM — that's a separate discussion)
- Cost optimization of haiku usage (user confirmed: focus on correctness, not cost)
- Changing hook architecture or latency (benchmarks show ~300ms avg is acceptable)

## Decisions

### Decision 1: Character-safe truncation via `cut -c` instead of `head -c`

**Choice**: Replace `head -c N` (byte-level) with `cut -c1-N` (character-level) for all truncation of user prompt content.

**Alternatives considered:**
- `python3 -c "print(sys.stdin.read()[:N])"` — correct but adds ~50ms Python startup per call
- `head -c N | iconv -c -t utf-8` — strips invalid bytes after truncation, but may produce incomplete text
- `cut -c1-N` — POSIX character-level cut, no Python overhead, correct for multi-byte UTF-8 in UTF-8 locale

**Rationale**: `cut -c` operates on characters (respecting `LC_CTYPE`), not bytes. It's a drop-in replacement for `head -c` with zero additional overhead. Requires `LANG` or `LC_CTYPE` to be set to a UTF-8 locale, which is the default on all our target systems.

### Decision 2: Defense-in-depth surrogate sanitization in `cmd_remember`

**Choice**: Add `content.encode('utf-8', errors='replace').decode('utf-8')` in the Python inline script before calling `m.remember()`.

**Alternatives considered:**
- Sanitize only at the source (wt-hook-memory) — misses other callers of `set-memory remember`
- Validate and reject (raise error) — better to save with replacement char (U+FFFD) than lose the entire memory
- Sanitize in bash before passing env var — bash can't reliably detect surrogates

**Rationale**: This is the last defense line before Rust. Even if all upstream sources are fixed, a future caller could introduce surrogates. The replacement character `�` preserves the memory with minimal data loss.

### Decision 3: Replace `except Exception: pass` with logged error

**Choice**: In `_stop_raw_filter()` line 1078, catch `UnicodeEncodeError` specifically, log it to stderr (which goes to `$STOP_LOG_FILE`), and continue processing remaining entries.

**Rationale**: Silent swallowing prevents diagnosis. Logging enables monitoring. Continuing (not crashing) ensures partial extraction still works.

### Decision 4: Sanitize transcript JSON content after `json.loads()`

**Choice**: After reading each JSONL line with `json.loads()`, sanitize string content by replacing surrogates: `content.encode('utf-8', errors='surrogateescape').decode('utf-8', errors='replace')`.

**Rationale**: Node.js can emit unpaired surrogates in JSON. Python's `json.loads()` faithfully decodes them. We need to clean them before they propagate through the pipeline. Using `surrogateescape` → `replace` handles the specific case of lone surrogates without affecting valid text.

### Decision 5: RocksDB LOG.old cleanup via `set-memory cleanup-logs`

**Choice**: Add a `cleanup-logs` subcommand to `set-memory` that removes LOG.old files older than 24 hours. Call it at the start of the Stop hook (before extraction, once per session).

**Alternatives considered:**
- Cron job — adds external dependency, not self-contained
- Fix in shodh-memory Rust (`keep_log_file_num=5`) — correct long-term fix, but requires upstream change
- Delete on every hook call — too aggressive, may interfere with active RocksDB operations

**Rationale**: Once-per-session cleanup is lightweight and self-contained. The 24-hour age threshold avoids deleting logs from concurrent operations.

### Decision 6: Stronger CLAUDE.md citation instruction

**Choice**: Add a numbered action list in the Persistent Memory section:
1. "When you receive memory context in system-reminder tags, FIRST scan for directly relevant memories"
2. "If a memory answers the question or provides a known fix, cite it: 'From memory: ...'"
3. "Do NOT re-investigate problems that have a known solution in memory"

**Rationale**: The current instruction is a single dense paragraph. A numbered action list is harder to skip and more explicit about the expected behavior.

## Risks / Trade-offs

- **`cut -c` locale dependency** → Mitigation: all target systems have UTF-8 locale. Add `export LC_ALL=C.UTF-8` fallback in the hook if `LANG` is unset.
- **Replacement characters in saved memories** → Acceptable trade-off: `U+FFFD` (�) in rare edge cases is better than losing the entire memory. These would only appear when surrogates slip through all other defenses.
- **LOG.old cleanup timing** → Low risk: `find -mmin +1440 -delete` runs in <100ms and only touches old files. RocksDB doesn't read LOG.old files after creating them.
- **CLAUDE.md instruction effectiveness** → Uncertain: stronger wording may not change LLM behavior. But it's zero-cost to try and the current 0.1% citation rate can only go up.
