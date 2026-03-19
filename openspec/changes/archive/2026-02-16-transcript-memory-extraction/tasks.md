## 1. Refactor stdin handling in wt-hook-memory-save

- [x] 1.1 Replace `cat > /dev/null` with stdin JSON parsing: extract `transcript_path`, `stop_hook_active`, and `session_id`
- [x] 1.2 Add `stop_hook_active` guard — exit 0 immediately if true

## 2. Transcript skill detection

- [x] 2.1 Add function to scan transcript JSONL for opsx/openspec skill invocations (grep for `"skill":"opsx:` and `"skill":"openspec-`)
- [x] 2.2 Extract change name(s) from detected skill invocations for tagging
- [x] 2.3 Skip extraction if no skills detected (fall through to existing commit-based logic)

## 3. Agent deduplication check

- [x] 3.1 Scan transcript for evidence of agent memory saves (`set-memory remember` calls, `[Memory saved:`, `[Agent insights saved:`)
- [x] 3.2 Set a flag indicating whether agent already saved (used to adjust the extraction prompt)

## 4. LLM extraction via claude CLI

- [x] 4.1 Extract last ~100 lines of transcript JSONL into a temp file
- [x] 4.2 Write the extraction prompt (structured: identify errors, user corrections, patterns, decisions; max 5 insights; output format `Type|tags|content`)
- [x] 4.3 Call `CLAUDECODE= claude -p --model haiku` with the prompt and transcript context, capture output
- [x] 4.4 Handle failure/timeout/empty output gracefully (exit 0)

## 5. Save extracted insights to set-memory

- [x] 5.1 Parse LLM output lines in `Type|tags|content` format
- [x] 5.2 Validate each line (skip malformed lines, cap at 5 insights)
- [x] 5.3 Call `set-memory remember --type <Type> --tags <tags>` for each valid insight

## 6. Integration with existing commit-based logic

- [x] 6.1 Ensure existing commit-based design choice extraction still runs after/alongside transcript extraction
- [x] 6.2 Test both paths can execute independently in the same hook invocation
