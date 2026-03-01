# Proposal: Sentinel Optimization

## Problem

The sentinel skill's poll loop runs as a single long-running bash command with a 10-minute timeout. While the bash loop itself is cheap (no LLM cost), the problem is:

1. **Blocking**: While the poll loop bash command runs, the Claude Code UI is blocked — user messages queue up and only process after the loop breaks or times out. The user must press Esc to interrupt.

2. **Expensive thinking**: After each poll loop break, the sentinel re-analyzes the full context (often 300k+ tokens) with Opus thinking, taking 15+ minutes just to decide "everything is fine, restart the poll loop."

3. **Slow responsiveness**: The user cannot interact with the sentinel while it's polling. A simple "how's it going?" requires waiting for the current poll cycle to end.

## Solution

Redesign the sentinel to use **short, non-blocking poll cycles** instead of a long-running bash loop:

1. **Single-shot poll**: Replace the 10-minute bash while-loop with a single state check that returns immediately. The sentinel reads state, makes a decision, and either acts or starts the next poll after a brief pause.

2. **Background polling**: Use `run_in_background` for the sleep+check cycle so the user can interact with the sentinel between polls.

3. **Lightweight status checks**: The poll itself should be a simple bash one-liner (read JSON, echo event), not a loop. The LLM decides what to do next based on the result — but most decisions are trivial ("still running → poll again").

## Scope

- Modify `.claude/commands/wt/sentinel.md` skill prompt
- No changes to `wt-orchestrate` itself
- No changes to `wt-loop`

## Out of Scope

- Model selection (haiku vs opus) — Claude Code doesn't support mid-session model switching
- Orchestrator architecture changes
