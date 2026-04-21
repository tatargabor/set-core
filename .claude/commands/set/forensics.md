Forensic analysis of a completed orchestration run.

**Input**: `<run-id>` (the e2e-runs directory name, e.g. `craftbrew-run-20260421-0025`). If omitted, ask the user which run to analyse.

**You are debugging a completed orchestration run.** Use `set-run-logs` to surface filtered views over Claude Code session transcripts + orchestration logs without dragging raw 300+ KB jsonl files into context.

## CRITICAL: never read raw session jsonl unbounded

A single session jsonl can exceed 300 KB; a run has 50+ sessions. Always use the CLI's filtered views FIRST. Only fall back to `Read` on a specific line range after the CLI has narrowed the suspect.

## Triage flow (follow in order)

1. **Discover**:
   ```bash
   set-run-logs <run-id> discover
   ```
   Confirms which session dirs (main + each worktree) and orchestration artifacts were found.

2. **Digest** — get the error map:
   ```bash
   set-run-logs <run-id> digest
   ```
   Aggregates `tool_error`, `bash_nonzero_exit`, `stop_reason_anomaly`, `user_interrupt`, `permission_denial`, and `crash_suspect` signals across every session, grouped by change → session → tool with snippets and counts.

3. **Drill into suspect sessions** — for each suspect from the digest:
   ```bash
   set-run-logs <run-id> session <uuid-prefix> --errors-only
   ```
   The UUID prefix from the digest (e.g. `531d481b`) is enough — minimum 6 chars. Use `--tool <Bash|Edit|Read|...>` to narrow further.

4. **Targeted probes** — when a specific error signature matters:
   ```bash
   set-run-logs <run-id> grep "<pattern>"
   set-run-logs <run-id> grep "EACCES" --tool Bash
   set-run-logs <run-id> grep "MaxToken" -i --limit 100
   ```
   Emits only the matching `message.content` text, never raw jsonl. Default cap is 50 matches — raise with `--limit` only when you must.

5. **Cross-reference orchestration timing**:
   ```bash
   set-run-logs <run-id> orchestration
   ```
   Per-change dispatch counts, last gate status, terminal status (e.g. `MERGE_SUCCESS`, `FIX_ISS_ESCALATED`), gate-outcome totals. Use this to map a suspect session back to the engine's view.

6. **Raw jsonl — last resort only.** Use `discover` output to find the exact path, then `Read` with `offset` + `limit`. Never read a whole session jsonl.

## Output to user

Summarise findings in this structure:

```
## Run summary
- Resolved: N session dirs (main + worktrees), orchestration logs (found/missing)
- Sessions scanned: M, total error signals: K
- Terminal status by change: ...

## Top error patterns
1. <pattern> in <change>/<session> × N — <one-line snippet>
2. ...

## Suspect sessions
- <change>/<short-uuid>: <reason> (next: `set-run-logs <run-id> session <uuid> --errors-only`)
```

Then propose the next debugging step (e.g. "shall I drill into session X?" or "the lint gate failed on Y — let's grep for it").

## When NOT to use

- For an in-flight run — that's the sentinel's job, not forensics.
- For cross-run comparison — `set-compare run-a run-b` instead.
- To analyse code quality or implementation details — this is for runtime / orchestration debugging only.
