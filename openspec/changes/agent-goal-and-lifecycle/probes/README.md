# Probes — the reproducers for `measurements.md`

A measurement is a claim with a timestamp; a probe is what lets a later reader disagree with it.
Every figure in `../measurements.md` came from one of these, and they are kept because the
runtime they measure changes underneath us — a keystroke into a TUI is a version-fragile
interface, and a number nobody can re-take is a number nobody can correct.

Each script starts a real `claude` under `pty.fork()`, drives it, and reports. They need a
terminal-free environment and a working `claude` on `PATH`. Set `PROBE_DIR` to choose where the
scratch trees go; without it each run makes its own temporary directory.

    PROBE_DIR=/tmp/agent-goal-probe python3 probe_rotate.py

| probe | what it answers | the measurement it produced |
|---|---|---|
| `probe_rotate.py` | does `/clear` keep the process? | M1 / task 1.4 — same pid and starttime token, 1 transcript before → 2 after, on `claude --dangerously-skip-permissions` / `claude-opus-5` |
| `probe_hooks.py` | which hooks fire, and do any carry `context_window`? | task 1.1 — 8 of 9 hooks fired, `context_window` in the statusline payload alone |
| `probe_turn.py` | can "between turns" be established, in BOTH directions? | task 1.2 — the `UserPromptSubmit`/`Stop` pair discriminates; the transcript tail does not, and fails open |
| `probe_settings.py` | does `--settings` carry the reader without writing into the tree? | task 1.3 — tree byte-identical; hooks merge additively, `statusLine` is overridden |
| `probe_sub.py` | what trace does a spawned agent leave? | M3 — the parent records an `Agent` tool call with an `agentId`; the child writes no transcript, and `isSidechain` stays 0 |

## Two things to know before believing a run

**A first run in a fresh directory hits the trust prompt** and will sit there until it is
answered; the probes send a bare `\r` for it. If a probe reports nothing at all, that dialog is
the first thing to check on the captured screen.

**`CLAUDE_CODE_CHILD_SESSION` must not be inherited.** A probe started from inside an agent
session inherits it, the child writes **no transcript**, and every transcript-based assertion
then measures an empty set while looking exactly like a clean run. The probes unset it; that
contrast is itself one of M3's measurements.
