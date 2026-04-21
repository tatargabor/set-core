## Why

After every E2E orchestration run, debugging is a manual spelunk through dozens of Claude Code session transcripts — per-change worktree dirs each hold 10-30 session `*.jsonl` files of 20-300 KB apiece. An agent asked "what went wrong in this run?" has no way to answer without dragging hundreds of KB of raw transcripts into its context window, and a human has no single command that says "here are the errors across every agent that ran in this run." The orchestration-level logs (`orchestration-events.jsonl`, `orchestration-state-events.jsonl`) already summarise dispatches and gate outcomes, but they don't cover what actually happened inside each LLM session — tool errors, non-zero exits, permission denials, agent crashes, and the stop-reasons that preceded them. Without a structured forensic entry-point, post-run debugging wastes context on every run and the same patterns have to be re-derived each time.

## What Changes

- **New CLI `set-run-logs <run-id>`** — a framework-level command that, given an E2E run id, locates every Claude Code session transcript that belonged to that run (the main run dir plus every `-wt-<change>` worktree session dir under `~/.claude/projects/`), plus the orchestration-level log files under `~/.local/share/set-core/e2e-runs/<run-id>/`, and exposes filtering/aggregation subcommands.
- **Subcommand `discover`** — lists resolved session dirs with jsonl counts and sizes, plus the orchestration-level files. First-step sanity check; no content read.
- **Subcommand `digest`** — aggregates error/anomaly signals across all session jsonls: `tool_use` results with `is_error:true`, non-zero Bash exit codes extracted from tool results, `stop_reason` anomalies (`max_tokens`, `tool_use_error`, `refusal`), explicit user interrupts, permission denials, and agent-process crashes. Groups results by change → session → tool and emits compact markdown the agent can read directly.
- **Subcommand `session <uuid>`** — targeted view of a single session: tool-call timeline with pass/fail outcomes, filterable to errors only. Used after `digest` flags a suspect session.
- **Subcommand `grep <pattern>`** — regex search across jsonl contents but emits only the matching `message.content` text (not the whole jsonl line), so agents can probe for a specific error signature without loading 300 KB transcripts.
- **Subcommand `orchestration`** — summarises `orchestration-events.jsonl` + `orchestration-state-events.jsonl`: dispatches, gate outcomes, state transitions, terminal statuses. Bridges the per-session view with the orchestration-level view so timing can be cross-referenced.
- **New skill `/set:forensics`** — a short procedural skill (`.claude/skills/set/forensics/SKILL.md`) that teaches the agent to start with `digest`, drill into suspect sessions via `session <uuid>` before ever reading raw jsonl, use `grep` for targeted probes, and cross-reference orchestration events for timing. The skill captures the standard triage order so it doesn't have to be re-derived every run.
- **Capability-guide registration** — the new skill is listed in `.claude/rules/capability-guide.md` and mentioned in `/set:help`.

## Capabilities

### New Capabilities
- `run-forensics` — structured forensic entry-point for a completed orchestration run: resolves all session transcripts + orchestration logs, aggregates error signals, and exposes filtered views that keep debug work context-efficient.

### Modified Capabilities
- None. (`capability-guide.md` and `/set:help` are documentation surfaces, not spec-owned capabilities.)

## Impact

- **New CLI entry**: `bin/set-run-logs` (new file, Bash or Python wrapper around the logic module).
- **New core logic module**: `lib/set_orch/forensics/` (new package — transcript discovery, jsonl filtering, aggregation helpers). Project-agnostic (Claude Code harness concern, not project-type concern), so it stays in core (Layer 1) per the modular-architecture rule.
- **New skill**: `.claude/skills/set/forensics/SKILL.md` (new file).
- **Capability-guide edit**: `.claude/rules/capability-guide.md` gains one row under the command table.
- **Help edit**: `.claude/skills/set/help/SKILL.md` (or equivalent) gains a one-line reference.
- **No state/schema changes.** The forensics tooling is read-only against existing log artifacts — no new files written, no state mutations.
- **No changes** to orchestration engine, profile system, MCP surface, web API, or consumer scaffolds.
