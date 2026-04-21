---
name: set:forensics
description: Forensic analysis of a completed orchestration run. Use this for post-run debugging, error triage, and digging into what an agent actually did inside a session — without dragging raw 300 KB jsonl transcripts into context.
---

# /set:forensics — Run forensics

Triage what failed in a completed orchestration run using filtered views over Claude Code session transcripts and orchestration logs.

**WARNING — never read raw session jsonl files unbounded.** A single session jsonl can exceed 300 KB and a run typically has 50+ sessions. Always go through the CLI's filtered views first; only fall back to raw `Read` on a specific line range when the CLI has narrowed the suspect.

## Triage order

Always follow this sequence:

1. **`set-run-logs <run-id> discover`** — confirm the scope of resolved sources. Verify the main session dir and every `-wt-<change>` worktree dir was found, plus the orchestration dir.

2. **`set-run-logs <run-id> digest`** — get the error map. Aggregates tool errors, non-zero bash exits, stop-reason anomalies, user interrupts, permission denials, and crash suspects across every session. Output is grouped by change → session → tool with snippets.

3. **`set-run-logs <run-id> session <uuid> --errors-only`** — for each suspect session in the digest, view its tool-call timeline filtered to errors. Use the short UUID prefix (≥6 chars) from the digest. Only AFTER you've narrowed via this view should you read raw jsonl.

4. **`set-run-logs <run-id> grep <pattern>`** — targeted probe for a specific error signature across all sessions. Emits ONLY the matching `message.content` text (not raw jsonl lines), so it's safe to use in agent context. Default cap is 50 matches — pass `--limit` to raise.

5. **`set-run-logs <run-id> orchestration`** — cross-reference timing. Shows per-change dispatch counts, last gate status, terminal status, gate-outcome counts. Use this to map a suspect session back to its orchestration timeline (when it dispatched, which gate triggered, what the terminal status was).

6. **Raw jsonl as last resort.** If the CLI's filtered views still leave a question unanswered, locate the specific jsonl from `discover` output and `Read` only the line range you need. Never `Read` a session jsonl without an offset/limit.

## Common subcommand options

- `--json` — emit JSON instead of markdown (for piping to `jq` or programmatic consumers).
- `session --tool <name>` — filter a session timeline to a single tool (e.g. `--tool Bash`).
- `grep -i` — case-insensitive search.
- `grep --tool <name>` — restrict grep to one tool's `tool_use` / `tool_result` blocks.
- `grep --limit <N>` — raise the default 50-match cap (use sparingly to protect context).

## When to use

- After any orchestration run that didn't merge cleanly.
- When the user asks "what happened in run X?" / "why did change Y fail?" / "did agent Z get stuck?".
- Before reading any session jsonl by hand.
- When investigating a finding from the verify gate — find the agent session that produced the failing commit.

## When NOT to use

- For an in-flight run — the sentinel owns live monitoring; this targets completed runs.
- For cross-run comparison — use `set-compare` instead.
- For project-type-specific analysis — this CLI is project-agnostic.

## Quick reference

```bash
set-run-logs <run-id> discover                          # what's there
set-run-logs <run-id> digest                            # error map
set-run-logs <run-id> session <uuid> --errors-only      # one session's errors
set-run-logs <run-id> grep <pattern> [--tool <name>]    # targeted probe
set-run-logs <run-id> orchestration                     # engine-level summary
```

Pair every drill-down with the orchestration view to align session events with dispatch / gate timing. Don't read raw jsonl until the CLI has narrowed the suspect.
