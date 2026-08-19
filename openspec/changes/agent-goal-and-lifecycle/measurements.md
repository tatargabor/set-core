# Measurements — agent goal & lifecycle, 2026-08-19

Recorded at the moment of measurement. Every claim below names the command or the artifact that
produced it. Claude Code **2.1.235**, model under probe `claude-haiku-4-5-20251001`.

## M1 — Can an agent be cleared without losing its process?

**YES, and this reverses the assumption the discussion started from.**

Probe: `pty.fork()` → `claude` in a scratch directory, one turn, `/clear`, one more turn.

- pid **1701204** before and after; `/proc/<pid>/stat` starttime token **101626821** unchanged.
- Session logs in that directory: **1 before the clear, 2 after** —
  `0fbad12b-…` then `0738df7c-…`.

So `/clear` **rotates the session id and the transcript file inside the same process**. The pty,
the process, the terminal view and therefore the fleet slot all survive; only the conversation is
replaced. An agent cannot clear *itself* from inside its own turn, but the framework, which owns
the pty for the agents it starts, can write `/clear` into it and then feed the handoff back.

### The archive agrees, and shows the fail direction

`grep -l 'command-name>/clear'` over 98 transcripts → 11 files. **10 real, 1 false**: the eleventh
was a `/clear` quoted inside a `tool_result` — the measurement matching a quotation of its own
subject. In all 10 real cases the `/clear` is at **index 3 of a NEW file**, and the gap between the
predecessor's last line and the successor's first is **0.0 s / 2.8 s / 5.2 s** in three of them.
A fresh process launch cannot be 0.0 s.

## M2 — Does anything see an agent's remaining context?

**YES, and better than expected: the harness hands it to a hook on every render.**

Captured payload (project-local `statusLine` command dumping stdin):

    context_window: { total_input_tokens: 34515, total_output_tokens: 146,
                      context_window_size: 200000,
                      used_percentage: 17, remaining_percentage: 83 }
    top-level keys: session_id, transcript_path, cwd, prompt_id, session_name, model,
                    workspace, version, output_style, cost, context_window,
                    exceeds_200k_tokens, fast_mode, thinking, rate_limits

`context_window_size` is **reported per model**, so the framework needs no constant. This matters:
the existing `context-window-metrics` capability hardcodes 200 000 and reads from
`loop-state.json` — that constant is already wrong for a 1M-context session.

⚠ `agents` is **not a key of this payload**, yet `~/.claude/statusline.sh:26` reads `.agents // []`.
That is a zero produced by a missing key, not by an empty list — the shape-error class. Measured on
one probe with no subagent running; whether the key appears when one does is NOT established here.

## M3 — What trace does a spawned agent leave?

**Three separate answers, and only one of them was what I expected.**

1. **A child session writes no transcript at all.** Controlled contrast, same command, same
   directory: with `CLAUDE_CODE_CHILD_SESSION` inherited → **0** transcript files; with it removed
   → **2**. The startup banner states it: `⚠ Transcript saving is off — inherited
   CLAUDE_CODE_CHILD_SESSION marker`. This confirms `fleet-view/design.md` §6.3 by measurement.
2. **The parent records the ACT, not the conversation.** A probe that spawned one subagent produced
   in the parent transcript a `tool_use` named **`Agent`** with `{subagent_type, description,
   prompt}`, and a `tool_result` carrying an `agentId`. `isSidechain` stayed **0** — the child's
   turns are nowhere.
3. **A live count exists:** `pendingBackgroundAgentCount`, observed with values 1 and 2.

### ⚠ My own first measurement of this was wrong, in the reassuring direction

I grepped the 98 transcripts for a `tool_use` named **`Task`** and got **0**, and was one step from
concluding that subagents leave no trace in this repository. The tool is named **`Agent`**. Re-run
with the right name: **11 calls in 4 transcripts** — 6 `general-purpose`, 5 `fork`.

The refuted pattern is the durable half: a tool-name string is a second copy of an interface, and
mine drifted. The corrected number is cheap; the lesson is that a zero from a name-match must be
proven to be able to fire before it is believed.

## What these decide about the change

- **The successor is not a new process.** Item (5) — "does the successor take the predecessor's
  slot?" — is answered by M1: same pid, same pty, same label. Continuity is the cheap default;
  `fleet-view` task 7.5 already keys the open terminal by LABEL rather than pid.
- **The trigger is measurable without asking the agent.** M2 gives remaining context per model.
- **Descendants must be counted from the ACT, not from processes or transcripts.** M3 says the
  child leaves no transcript and no sidechain; the parent's `Agent` tool call is the only record,
  and a `claude -p` child that has exited leaves no process either. This is the same conclusion
  `fleet-view` task 2.5 reached for the upward direction (`requested_by`, recorded at the act).

## M4 — The alternative that already exists: the harness compacts and carries on

Recorded because the change must justify itself against it, not against a straw man.

Scanning 98 transcripts for `isCompactSummary`: one session file — `7e357045-…`, **15 304 lines** —
contains **11 compact summaries under a single session id**. So a session whose context fills is not
replaced and does not stop; the harness compacts it in place and continues.

The rotation in this change is therefore **not** a rescue from death. It is a choice between two
carriers across the same boundary: an automatic compaction, which keeps confidence and loses
precision (this repository's own standing warning about compounding), and a written handoff that can
be read back and disagreed with. That is the argument the change rests on, and it is a weaker claim
than "otherwise the agent dies" — deliberately, because the stronger one is false.

## M5 — Settings can be supplied from outside the project tree

`claude --help`: **`--settings <file-or-json>`** — a settings file path or a JSON string. So the
statusline carrier that reports context back to the framework can be handed to a framework-started
agent from a framework-owned location, and **nothing is written into the project's tree**. This
matters here more than it looks: every write path into a consumer tree in this repository is guarded
by an ownership ledger, and the cheapest way to satisfy that guard is not to be a write path.

---

# Group 1 measurements — the two carriers, 2026-08-19

Probe: `claude` under `pty.fork()` in a scratch directory whose project-local settings register a
dump command for **nine hooks** and for the statusline, each appending its raw stdin with a
timestamp. Model `claude-haiku-4-5-20251001`.

## 1.1 — Does a hook carry the context figures? NO. The statusline is the only carrier.

Eight of the nine hooks fired across a 50 s session. Their payload keys, in the order they fired:

| t+s | hook | keys |
|---|---|---|
| 0.00 | `SessionStart` | cwd, hook_event_name, model, session_id, source, transcript_path |
| 15.16 | `UserPromptSubmit` | + permission_mode, prompt, prompt_id |
| 17.39 | `PreToolUse` | + tool_input, tool_name, tool_use_id |
| 29.45 | `PostToolUse` | + duration_ms, tool_response |
| 30.82 | `Stop` | + background_tasks, last_assistant_message, session_crons, stop_hook_active |
| 34.60 | `SubagentStop` | + agent_id, agent_transcript_path, agent_type |
| 50.19 | `SessionEnd` | + reason |

`grep -l context_window` over every dump → **`StatusLine.jsonl` only**. No hook carries the window
size, the usage, or the percentages. **The carrier is decided: the statusline.**

`PreCompact` and `Notification` did not fire in this probe and are therefore **not measured**.
`PreCompact` is worth a later look: it fires exactly when the runtime is about to compact, which is
the event a threshold is a proxy for — but no hook measured here carries the figures, so it is a
hypothesis, not a plan.

### Cadence: event-driven, not a timer — and that is adequate for the reason that matters

**5 renders in 56 s**, gaps between **3.0 s and 20.8 s**. So a threshold is checked at roughly
turn granularity, not continuously. That is enough *because a rotation can only happen between
turns anyway* (D5) — the reading's granularity matches the act it gates, rather than merely being
"fast enough".

### ⚠ The first render carries a size and NO usage, and a naive division reads it as 0 %

    t+0.0s   context_window_size=200000  total_input_tokens=0
             current_usage=null  used_percentage=null  remaining_percentage=null

Observed in **1 of 5** renders — the one at session start. Dividing `total_input_tokens` by the
size yields **0 %**, i.e. *plenty of room*, for a reading that does not exist. This is the
false-value class in its reassuring direction, and it is why the spec requires `unknown` to be a
value rather than a number: the shipped statusline's own `// empty` fallbacks would render this as
blank, and any arithmetic on it as zero.

## 1.2 — Turn state: the hook pair works, the transcript tail is REFUTED and fails open

32 samples at ~1 s, across two deliberately different turns: one 14 s turn with a tool call, and one
sub-second text-only turn. Two candidate signals sampled at each point.

**Signal A — the hook pair** (the last of `UserPromptSubmit` / `Stop` before the sample):

| truth | readings |
|---|---|
| BUSY | `BUSY` ×15, `no-event-yet` ×1 |
| IDLE | `IDLE` ×7, `no-event-yet` ×3 |

The only value appearing on both sides is **no event yet**, which is honest unknown rather than a
wrong answer, and it occurs only before the session's first prompt. The one BUSY sample carrying it
was taken *before* the submit hook fired — the label was optimistic, not the signal wrong. On the
sub-second turn the pair read `BUSY` **exactly during it** and `IDLE` on either side, so its
resolution is better than the turn it has to catch.

**Signal B — the transcript tail** (last row type): **refuted, and in the dangerous direction.**

| truth | readings |
|---|---|
| BUSY | `assistant/tool_use` ×10, `ai-title` ×5, `last-prompt` ×1 |
| IDLE | `system` ×4, `atis-latch` ×3, `last-prompt` ×3 |

Two separate failures. It overlaps on `last-prompt`. And on the **text-only turn the tail never
became `assistant/tool_use` at all** — it read `attachment`, then `atis-latch` — so the obvious rule
*"busy iff the tail is a tool call"* reports IDLE while the agent is answering. That failure sends
the clear mid-turn, which is exactly the damage the gate exists to prevent. The row types it does
show (`ai-title`, `atis-latch`, `attachment`) are the runtime's internal bookkeeping, not turn
markers; the tail correlated with turn state without being about it.

**`pendingBackgroundAgentCount` was `None` throughout** — it counts background agents, not turns.
Dropped as a candidate.

**Decision: the framework maintains turn state from its own `UserPromptSubmit` / `Stop` hooks**,
installed through `--settings` (task 1.3), and treats *no event yet* as unknown, which blocks the
clear.

## Two findings this probe produced that nobody asked it for

**`SubagentStop` fires for work no one spawned, and names a transcript that does not exist.** In a
session with no subagent, it fired 3.8 s after `Stop` with `agent_type: ""` (empty) and an
`agent_transcript_path` pointing at a file that **is not on disk**. Two consequences: descendant
accounting built on this hook would count phantom children, and the missing file independently
confirms M3 — the runtime names where a child's transcript *would* go, and the child does not write
one.

**`Stop` carries `last_assistant_message`** — the agent's final text, verbatim. Any hook that logs
its own payload is therefore a persistence path for conversation content, which the confidentiality
boundary forbids. The framework's own hooks must record the *event*, never the payload.
