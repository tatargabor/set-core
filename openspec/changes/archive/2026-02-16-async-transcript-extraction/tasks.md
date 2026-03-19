## Tasks

- [x] Create `run_extraction_background()` wrapper function in `wt-hook-memory-save` that handles lockfile acquire, calls `extract_from_transcript`, and cleans up lock+tmpfile on exit via trap
- [x] Add lockfile logic: check `.set-core/.transcript-extraction.lock`, validate PID alive with `kill -0`, skip if active, remove if stale
- [x] Move the `extract_from_transcript` call site (lines 266-270) to use `run_extraction_background "$TRANSCRIPT_PATH" &` + `disown`
- [x] Move tmpfile creation and trap from inside `extract_from_transcript` into `run_extraction_background` (background process owns its own cleanup)
- [x] Add error logging: redirect background stderr to `.set-core/transcript-extraction.log` (append mode, with timestamp)
- [x] Test: verify hook exits immediately (< 1s) when transcript extraction is triggered
- [x] Test: verify lockfile prevents concurrent extractions (simulate with sleep)
