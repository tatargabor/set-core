# Proposal: Sentinel Supervisor Redesign — Python Daemon + Ephemeral Claude

## Why

The current sentinel is a long-lived Claude conversation (`claude -p --max-turns 500`) that polls orchestration state every 120 seconds. In practice it:

1. **Eats context and dies after 30-40 minutes**. Every poll is a turn. Every turn appends the full Bash command and tool_result to the conversation. After ~30-40 polls, the 1M cache window is exhausted and the Claude CLI exits silently. During the 2026-04-11 micro validation run, the sentinel died cleanly after 36 minutes and the run continued unsupervised for the remaining hour. The orchestrator happened to finish without needing intervention, but if it had crashed, nothing would have restarted it.

2. **Burns tokens on idle polling**. The sentinel spends ~95% of its turns printing "Orchestration running (X/Y changes, Z tokens). Polling…" and then sleeping 120 seconds. Each of those no-op turns still includes the full Bash tool invocation, the tool result, and a user-facing line in the conversation context. The 36-minute run consumed roughly 150-300k tokens of context and zero tool calls of actual value — no Tier 3 intervention happened, no checkpoint decision, no crash restart, no stall diagnosis, no finding logged.

3. **Cannot supervise long runs**. Any orchestration over 40 minutes outlives its supervisor. A 4-hour spec decomposition with 20 changes runs without a sentinel for the vast majority of its lifetime, defeating the purpose of having one.

4. **Produces low-value output**. The sentinel's real value is in Tier 3 intervention (integration-failed diagnosis, non-periodic checkpoint decisions, stall escalation, final completion report) — events that fire a handful of times per run, not every 2 minutes. The current architecture spends 40 turns polling empty state for every 1 turn doing actual work. The log audit over 4 recent orchestration runs (micro, minishop_0411, minishop_0410, minishop0411) confirmed that 95% of sentinel-logged findings are either structured state transitions that `jq` could extract or hand-coded patterns that an `if` statement in Python would cover. Novel, LLM-exclusive discoveries: 0-2 in the last 2 weeks.

The root cause is architectural: **we are asking an LLM to do a task that a small Python daemon could do**. Polling, process supervision, state monitoring, and heartbeat emission are all deterministic operations. Claude's value is open-ended reasoning — and that value is wasted when 95% of the turns are "check state, nothing changed, sleep".

## What

Replace the Claude-driven sentinel with a three-layer supervisor:

1. **Layer 1 — Python daemon (`set-supervisor`)**: a long-running Python process that starts the orchestrator, monitors it via cheap polling (process alive check, state.json mtime check, events.jsonl tail), and detects a small set of anomaly signals (crash, stall, integration-failed, unknown event type, log error rate spike). The daemon has no LLM calls on the routine path.

2. **Layer 2 — Ephemeral Claude trigger**: when Layer 1 detects an anomaly, it spawns a fresh `claude -p` subprocess with a narrow, task-specific prompt (e.g. "integration-failed on change X — diagnose and fix") and a single-shot budget. The ephemeral Claude runs one task, writes findings to the sentinel events file, and exits. Each spawn has zero context carried over from previous spawns.

3. **Layer 3 — Canary Claude check (periodic, 15-30 min)**: every 15 minutes regardless of events, Layer 1 spawns a fresh `claude -p` with a structured diff of "what happened since last check" (merged/failed changes, warn-level log counts, new event types, watchdog fires, token progress). The canary reads the diff and decides "looks fine" or "escalate". This preserves the open-ended LLM oversight the current sentinel attempts at every poll — but with bounded context (the diff, not the full history), bounded frequency (every 15 min, not every 2 min), and fresh state (no accumulation).

The combined cost of Layer 2+3 per 2-hour run is estimated at 30-80k tokens (vs 150-300k for the current sentinel), and the system never dies from context exhaustion because every Claude invocation is ephemeral.

Key design properties:

- **No long-lived Claude conversation.** All LLM invocations exit within seconds or minutes.
- **Python is the smoke detector, Claude is the firefighter.** Python's job is to detect that something is off; Claude's job is to figure out what and act. Python does not need to know every failure mode in advance — "smoke" signals (crash, stall, error spike, silence, unknown event) catch the anomaly regardless of root cause.
- **Canary preserves open-ended oversight.** The 15-minute canary gives Claude a scheduled chance to look at the big picture and escalate things the trigger signals missed.
- **Survives arbitrary-length runs.** A 4-hour run is just 240 Python poll cycles + 16 canary Claudes + N triggered Claudes. Nothing accumulates.
- **Manager API unchanged.** The web dashboard still calls `POST /api/<project>/sentinel/start` — the endpoint just invokes `set-supervisor` instead of `claude -p` with the sentinel skill.

## Impact

- **New module**: `lib/set_orch/supervisor/` — the Python daemon, probably ~500-800 lines split across `daemon.py`, `anomaly.py`, `triggers.py`, `canary.py`, `ephemeral.py`.
- **New CLI**: `set-supervisor --project <name> --spec <path>` — the systemd-style entry point.
- **Manager API**: point `/api/<project>/sentinel/start` at `set-supervisor` instead of `claude -p`. Drop the sentinel.md slash command (`/set:sentinel`) from the consumer `.claude/commands/set/` deployment, or reduce it to a thin wrapper that invokes the daemon.
- **Sentinel skill file**: `.claude/commands/set/sentinel.md` becomes vestigial or is deleted. The heartbeat/status/finding helpers stay as they are — the ephemeral Claude invocations can still call them.
- **Events**: new event types `SUPERVISOR_START`, `SUPERVISOR_TRIGGER`, `CANARY_CHECK`, `SUPERVISOR_RESTART`, `SUPERVISOR_STOP`. Emitted to the same `orchestration-events.jsonl` so the set-web dashboard picks them up.
- **Observability**: a new web-dashboard tab or panel showing "supervisor events" — when the daemon fired, what triggered each ephemeral Claude, what the canary said.
- **Consumer deployments**: `set-project init` needs to deploy `set-supervisor` configuration. The old sentinel.md skill is removed from the template.
- **Migration**: no state migration needed. Existing orchestrations pick up the new supervisor on the next sentinel start.
- **Rollback**: directive flag `supervisor_mode: "python" | "claude" | "off"` lets operators fall back to the old Claude sentinel if the Python daemon misbehaves. Default is `python` post-rollout.
- **Not in scope**: replacing the orchestrator's internal watchdog, merging `set-supervisor` into the orchestrator process, or changing the gate pipeline. The supervisor wraps the orchestrator, it does not replace its internals.
- **Related future work**: the Tier 3 ephemeral Claude invocations will use the same `lib/set_orch/llm_verdict.py` classifier helper that was added for gate output parsing — good reuse.
