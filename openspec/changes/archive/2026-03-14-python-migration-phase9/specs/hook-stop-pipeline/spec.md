## Purpose

Migrate `lib/hooks/stop.sh` (420 LOC) to `lib/set_hooks/stop.py`. The Stop hook fires at session end: flushes metrics, extracts insights from transcript, and saves commit-based memories.

## Requirements

### STOP-01: Metrics Flush
- `flush_metrics(cache_file, session_id, transcript_path)` writes session metrics
- Collect from cache: turn_count, tool_use counts, token estimates
- Scan transcript for citation counts (memory IDs referenced)
- Call `lib.metrics.flush_session()` for persistence

### STOP-02: Transcript Extraction
- `extract_insights(transcript_path)` processes raw JSONL transcript
- Scan for skill usage patterns (`opsx:*`, `openspec-*`)
- Call Claude CLI (haiku model) for cheap insight extraction
- Unset `CLAUDECODE` env var to avoid nesting check
- Save extracted insights as memories (type: Learning)

### STOP-03: Commit-Based Save
- `save_commit_memories(transcript_path)` scans for git commits in session
- Extract commit messages and associated file changes
- Save as memories tagged `source:commit`

### STOP-04: Session Checkpoint
- `save_checkpoint(cache_file, turn_range)` periodic checkpoint during long sessions
- Triggered by turn count threshold (every 10 turns)
- Save summary of files read/modified and topics discussed

### STOP-05: Unit Tests
- Test metrics flush with mock cache data
- Test transcript extraction with mock JSONL
- Test commit memory extraction
