## 1. Core Implementation

- [x] 1.1 Modify `cmd_proactive` inline Python in `bin/set-memory` (lines ~706-729): after `proactive_context()` call, count results with score >= 0.4, if fewer than `min(limit, 2)`, run `m.recall(context, limit=limit, mode='hybrid')` as fallback
- [x] 1.2 Implement dedup logic: compare first 50 chars of content between proactive and hybrid results, keep proactive version when duplicate
- [x] 1.3 Assign synthetic `relevance_score` of 0.35 to hybrid-only results, preserve original scores on proactive results
- [x] 1.4 Ensure combined results are capped at `limit` and output as JSON in same format

## 2. Testing

- [x] 2.1 Manual test: `set-memory proactive "levelibéka"` returns the "A levelibéka zöld" memory (was missing before)
- [x] 2.2 Manual test: `set-memory proactive "mac és alwaysontop"` still returns always-on-top memories (no regression)
- [x] 2.3 Manual test: `set-memory proactive "cross-platform compatibility"` returns same quality as before (happy path unchanged)
- [x] 2.4 End-to-end: type a short query in Claude Code session and verify PostToolUse/UserPromptSubmit hooks inject the fallback results as system-reminders
