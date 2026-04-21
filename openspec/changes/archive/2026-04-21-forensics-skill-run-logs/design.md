## Context

Every orchestration run produces two distinct log streams that together describe what happened:

1. **Orchestration-level** — under `~/.local/share/set-core/e2e-runs/<run-id>/`: `orchestration-events.jsonl` (dispatches, gate verdicts, state transitions), `orchestration-state-events.jsonl` (state mutations), `orchestration-plan.json` (the decomposed plan), `orchestration-state.json` (the current state), plus `journals/` and `messages/` dirs. These summarise the engine's decisions — "change X dispatched at T, gate review returned fail with findings Y."

2. **Per-session transcripts** — under `~/.claude/projects/<encoded-path>/*.jsonl`: one `.jsonl` per Claude Code session, where each line is a message record (user message, assistant message, tool call, tool result) with full content. For a run with 3 changes and ~10 agent invocations per change plus the sentinel's sessions, there are typically 30-80 session jsonl files scattered across one "main" dir (the orchestrator's own sessions) and N "worktree" dirs (one per `-wt-<change>` worktree, where the per-change agents ran).

Today debugging a failed run means:
- Manually encoding the run path to find `~/.claude/projects/` dirs.
- Guessing which worktrees belonged to the run.
- Running `ls | wc -l` to see how many sessions there are.
- Greping blindly for "error" or "failed" across hundreds of KB.
- Opening individual jsonl files in an editor and paging through them.

An agent asked to debug inherits all of this plus a context budget — pulling 3-5 session jsonls (each 200+ KB) fills the window before any reasoning can happen.

The orchestration-level logs are well-understood (they're structured and small enough to read whole) but the per-session transcripts are the blind spot. That's where tool errors, non-zero exits, and assistant stop-reasons actually live.

## Goals

- Give an agent a deterministic way to answer "what failed in run X?" in ≤5 tool calls, using filtered views that stay well below the context budget.
- Give a human operator the same entry-point as a CLI command, so interactive debugging and agent-driven debugging share the same tooling.
- Keep all logic framework-level and project-agnostic — the same command must work against any run produced by any project type.
- Separate DATA surfacing (the CLI) from REASONING (the skill). The CLI exposes filtered views; the skill teaches the triage order. They can evolve independently.

## Non-Goals

- **Not** adding an LLM-powered root-cause analyser. The CLI surfaces structured data; the agent (or human) reasons. Wrapping it in an LLM would make the CLI slow, expensive, and non-deterministic.
- **Not** live-tailing an in-flight run. The sentinel already owns in-flight monitoring; forensics targets completed runs where the state is settled.
- **Not** cross-run comparison — `set-compare` exists for that. If comparison becomes useful from forensics output, it can be wired later by piping two `--json` outputs to a diff tool.
- **Not** modifying Claude Code's transcript format or how the harness writes sessions. The CLI is a consumer of existing artifacts.
- **Not** building a web UI. The web dashboard at port 7400 already renders orchestration-level logs; forensics is the command-line complement for per-session transcript drill-down.
- **Not** a project-type plugin. Session jsonls are a Claude Code harness concern, not a web-vs-anything-else concern. Logic lives in `lib/set_orch/forensics/`, never in `modules/web/`.

## Decisions

### D1: Logic lives in `lib/set_orch/forensics/`, CLI is a thin wrapper

Session jsonls are written by the Claude Code harness and are identical in shape regardless of project type — a Python file, a Next.js page, a Rust crate all produce the same record format. This means the forensic logic is genuinely core-layer (Layer 1) under the modular-architecture rule. It does NOT belong in `modules/web/` or any plugin.

**Decision:** create `lib/set_orch/forensics/` with modules `resolver.py` (run-id → session dirs), `jsonl_reader.py` (streaming line iterator + record parser), `digest.py` (error signal aggregation), `timeline.py` (single-session view), `grep.py` (content-only match extraction), `orchestration.py` (orchestration-event summariser). The CLI at `bin/set-run-logs` is a thin Click/argparse wrapper that calls these modules.

**Alternatives considered:**
- Put logic in `bin/set-run-logs` directly as a single Python script. Rejected — not reusable from MCP tools or the web dashboard if we later want to surface the same data there; also harder to unit-test than a module.
- Put logic in `modules/web/forensics/`. Rejected — the logic is project-agnostic (see above) and placing it in a module violates the layering rule.

### D2: Stream jsonl line-by-line; never load full files

A single session jsonl can exceed 1 MB. Loading 30-80 of them fully before filtering would use ~50 MB of Python memory and force the CLI to be an async service. Streaming each line and emitting only filtered results keeps memory flat and the CLI trivially re-runnable.

**Decision:** `jsonl_reader.py` exposes an iterator `iter_records(path: Path) -> Iterator[Record]` that yields parsed records one at a time. Digest, grep, and timeline consume the iterator; they never hold the full session in memory.

**Trade-off:** if a single line is malformed (truncated write during a Claude Code crash), we skip it with a WARNING log and continue, rather than aborting the scan. This gives partial results instead of total failure.

### D3: Run-id → session dir mapping uses prefix matching, not exact name

The encoding Claude Code applies to session directory names turns `/home/tg/.local/share/set-core/e2e-runs/<run>/` into `-home-tg--local-share-set-core-e2e-runs-<run>`. For the main run dir that's exact-match. For worktrees it becomes `-home-tg--local-share-set-core-e2e-runs-<run>-wt-<change>`.

**Decision:** prefix-match on the base encoded path, then require the character immediately after to be either end-of-string (main) or `-` (worktree separator). This handles the main dir + all worktrees in one pass and rejects name-collision neighbours (e.g. `<run>x`).

**Alternative:** parse `set-core`'s run state and worktree registry to get the exact list of dirs. Rejected — adds a dependency on run state being readable (it usually is, but sessions outlive state deletion). Prefix matching works even after state cleanup.

### D4: Digest error signals are whitelisted, not heuristic

"Errors" in a Claude Code session can theoretically come from many places — tool outputs, assistant refusals, user aborts, harness-level failures. A heuristic "anything suspicious" scan would produce false positives and change behaviour silently if the transcript format evolves.

**Decision:** the digest enumerates a FIXED list of signal types (see the spec), each with a stable extraction rule. New signal types are added deliberately by amending the spec. The list is:

1. Tool-result `is_error:true`.
2. Bash exit codes != 0 (regex on result content).
3. `stop_reason` ∉ {`end_turn`, `tool_use`, `stop_sequence`}.
4. Explicit user interrupts (`isInterrupt:true` or equivalent marker).
5. Permission denials (regex on assistant/system text).
6. Crash proxies (last assistant message lacks a proper stop_reason).

**Trade-off:** this misses unknown error shapes. Mitigation: the `grep` subcommand exists precisely for when the digest's whitelist isn't enough — the agent can probe for arbitrary text signatures.

### D5: Skill separate from CLI, under set-core's set-skills dir

The CLI is framework code (`bin/`, `lib/`). The skill is agent instruction (`.claude/skills/set/forensics/SKILL.md`) — two different audiences, two different change cadences. Wrapping the skill into the CLI as inline docstring help would muddle this.

**Decision:** the skill is a standalone markdown file describing the triage flow, delivered via set-core's normal deploy path (`.claude/skills/set/` lands in consumer projects via `set-project init`). The CLI stays a pure data-surfacing tool.

**Alternative considered:** ship the skill as a CLI subcommand (`set-run-logs help triage`) that emits the instruction text. Rejected — skills are agent-discovered via Claude Code's skill registry, not discovered by scraping CLI help text.

### D6: Output is markdown by default, `--json` for piping

Markdown is immediately readable for a human and cheap for an agent to include in its context (structure = bullet points). JSON is the correct transport for piping to `jq` or feeding to a subsequent tool.

**Decision:** every subcommand defaults to markdown, every subcommand accepts `--json` for the same data. Internal representation is JSON-shaped dicts; the markdown writer is a thin formatter.

**Trade-off:** two formatters to maintain per subcommand. Acceptable — the JSON shape is the canonical representation, and markdown is a simple `to_markdown(data)` over a stable schema.

### D7: Content-only grep strips jsonl structure

A naive `grep` over `*.jsonl` matches the raw line including `"type":"tool_use"` keys, `"tool_use_id":"..."` values, base64-ish content encoding, etc. The agent gets a match that's 95% noise.

**Decision:** the grep subcommand parses each line as JSON, extracts the `message.content` field (the actual text the user/assistant/tool produced), applies the pattern to THAT, and emits only the text region around the match with up to 2 lines of surrounding context. The jsonl structural keys never reach output.

**Trade-off:** matching against structural fields (e.g. searching for a specific `tool_use_id`) isn't supported. Acceptable — that's what the `session <uuid>` subcommand is for.

### D8: Session UUID prefix resolution across all resolved dirs

After D1+D3, a run's sessions are spread across the main dir and N worktree dirs. An agent using `session <uuid>` shouldn't have to know which worktree a session came from.

**Decision:** `session <uuid>` searches all resolved dirs. If the prefix is unique across them, it resolves; if ambiguous, the CLI lists the full UUIDs + their change names and exits non-zero. Minimum prefix length is 6 chars — shorter prefixes are too collision-prone across 50+ sessions.

**Alternative considered:** require the user to pass `--change <name>` alongside the UUID. Rejected — UUIDs are effectively unique already; the extra flag is friction for no real safety gain.

## Risks / Trade-offs

- **[Risk]** Claude Code's session jsonl format changes, breaking the digest's field extraction. **Mitigation:** `jsonl_reader.py` isolates the parsing; changes touch one module. Unit tests on the digest use fixture jsonl files that cover current format; any breaking change to the format requires a corresponding fixture update.

- **[Risk]** Very large runs (hundreds of sessions) take long enough for `digest` to feel slow. **Mitigation:** streaming parse keeps memory flat; the 30-second target for 50 sessions × 200 KB has ~10x headroom before user discomfort. If users hit larger runs, parallelise across session dirs with `multiprocessing.Pool` (single-file-per-worker is cache-friendly and embarrassingly parallel). Not implemented in v1 — deferred until measured need.

- **[Risk]** The whitelist of error signals misses a new failure shape. **Mitigation:** `grep` is the escape hatch. The whitelist is additive and changes go through the spec — we accept false negatives over false positives.

- **[Risk]** Session resolution by prefix picks up a lingering dir from a deleted run whose name was reused. **Mitigation:** the `discover` output lists every resolved dir with its mtime, so the operator can spot a stale dir immediately. Not worth building a "is this dir actually from this run?" check — Claude Code gives us no such signal.

- **[Risk]** Forensics tool grows in scope to become a general-purpose "set-debug" umbrella. **Mitigation:** each subcommand's scope is nailed in the spec. Future functionality that isn't per-session + per-run gets a separate CLI (we already have `set-compare` for cross-run).

## Migration Plan

There is no state or schema migration. Forensics is read-only and additive.

Deploy order:
1. Land `lib/set_orch/forensics/` module + unit tests with fixture jsonl files.
2. Land `bin/set-run-logs` CLI entry point, wired to the module.
3. Land `.claude/skills/set/forensics/SKILL.md` skill.
4. Update `.claude/rules/capability-guide.md` + `/set:help` quick reference to mention the new skill.
5. Update `templates/core/` if the CLI needs to be deployed to consumer projects via `set-project init` (it does — consumer agents should be able to run `set-run-logs` against their own runs).

Rollback:
- Revert the commits. No state touches, no migrations, no backwards-compatibility concerns.

## Open Questions

- **Q1:** Should the CLI auto-resolve the "latest run" if no id is passed? Convenient for interactive use (`set-run-logs digest` vs `set-run-logs craftbrew-run-20260421-0025 digest`). Defer — easy to add later if the verbose form is annoying in practice.
- **Q2:** Should session-level timeline output include a `hash` of the tool input/output for dedup? Useful when an agent retries the same failing tool 20 times, but clutters output for common cases. Defer — start with simple per-entry rendering.
- **Q3:** Should the digest's "crash suspects" section also look at the PID registry to correlate with `kill` / `SIGTERM` signals logged in the orchestration events? Would tell the agent "this session didn't crash, the supervisor killed it." Defer — the orchestration subcommand shows terminal statuses; the agent can cross-reference manually in v1.

None of these block implementation.
