## 1. Commit staged extractions (runs before extraction)

- [x] 1.1 Add `commit_staged_files()` function: iterate `.set-core/.staged-extract-*` (excluding `.ts` files), skip file matching current transcript basename, parse Type|tags|content lines, call `set-memory remember` for each valid line (same caps: 5 insights + 2 conventions), delete staged file + its `.ts` file after commit
- [x] 1.2 Add stale detection: for staged files matching current transcript, check `.ts` file age (or file mtime fallback); if >1 hour, commit and delete before proceeding to extraction
- [x] 1.3 Call `commit_staged_files` at the start of `run_extraction_background()`, before `extract_from_transcript()`

## 2. Staging file write (replaces direct set-memory saves)

- [x] 2.1 In `extract_from_transcript()`, replace the `set-memory remember` loop with atomic staging write: write Haiku output to a temp file, then `mv` to `.set-core/.staged-extract-{transcript-basename}`
- [x] 2.2 Write current epoch seconds to `.set-core/.staged-extract-{transcript-basename}.ts` after successful staging

## 3. Debounce

- [x] 3.1 Add debounce check at the top of `extract_from_transcript()` (after skill detection, before Haiku call): read `.ts` file, if exists and age < 300 seconds, log skip and return 0
- [x] 3.2 Log debounce skips to `transcript-extraction.log` with "[DEBOUNCE]" prefix

## 4. Integration tests

- [x] 4.1 Create `tests/test_save_hook_staging.sh` with test harness: mock `set-memory` (records calls to a log file), mock `claude` CLI (returns canned Type|tags|content output), set up temp `.set-core/` directory, provide fake transcript files with opsx skill markers
- [x] 4.2 Test: first extraction creates staged file, no `set-memory remember` calls
- [x] 4.3 Test: second extraction overwrites staged file content
- [x] 4.4 Test: session switch (different transcript) commits old staged file — verify `set-memory remember` called with correct Type/tags/content
- [x] 4.5 Test: debounce skips extraction within 5-minute window — verify no `claude` CLI call
- [x] 4.6 Test: stale file (>1 hour, same session) auto-committed — verify `set-memory remember` called
- [x] 4.7 Test: no-opsx-skill transcript skips extraction entirely (existing behavior)
- [x] 4.8 Test: PATH 2 commit-based extraction still works independently
- [x] 4.9 Run full test suite, fix any failures
