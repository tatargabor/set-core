## 1. Core module scaffolding

- [x] 1.1 Create `lib/set_orch/forensics/__init__.py` exporting the public API (`resolve_run`, `digest_run`, `session_timeline`, `grep_content`, `orchestration_summary`) [REQ: resolve-all-session-dirs-for-a-run-id]
- [x] 1.2 Create `lib/set_orch/forensics/resolver.py` with `ResolvedRun` dataclass and `resolve_run(run_id: str) -> ResolvedRun` that prefix-matches `~/.claude/projects/` entries + requires end-of-string OR `-` boundary + resolves `~/.local/share/set-core/e2e-runs/<run-id>/` [REQ: resolve-all-session-dirs-for-a-run-id]
- [x] 1.3 Emit WARNING on stderr when orchestration dir missing, continue with sessions only; raise a dedicated error when no session dirs found at all [REQ: resolve-all-session-dirs-for-a-run-id]
- [x] 1.4 Unit tests for resolver: main+worktrees resolution, prefix-collision rejection, missing orchestration dir, no sessions at all [REQ: resolve-all-session-dirs-for-a-run-id]

## 2. Jsonl streaming reader

- [x] 2.1 Create `lib/set_orch/forensics/jsonl_reader.py` with `iter_records(path: Path) -> Iterator[Record]` that streams line-by-line and yields parsed dicts [REQ: digest-subcommand-aggregates-error-signals]
- [x] 2.2 Handle malformed/truncated lines by logging WARNING and skipping (never abort entire scan) [REQ: digest-subcommand-aggregates-error-signals]
- [x] 2.3 Extract `Record` helpers: `is_tool_result`, `is_error_result`, `extract_bash_exit_code`, `extract_stop_reason`, `is_user_interrupt`, `extract_text_content` [REQ: digest-subcommand-aggregates-error-signals]
- [x] 2.4 Unit tests with fixture jsonl files covering: tool_use + tool_result pairs, is_error:true, Bash exit codes, stop_reason variants, isInterrupt markers, malformed lines [REQ: digest-subcommand-aggregates-error-signals]

## 3. Digest aggregator

- [x] 3.1 Implement `lib/set_orch/forensics/digest.py::digest_run(resolved: ResolvedRun) -> DigestResult` that iterates every jsonl across every resolved session dir [REQ: digest-subcommand-aggregates-error-signals]
- [x] 3.2 Aggregate the whitelisted signals (tool errors, non-zero bash exits, stop_reason anomalies, user interrupts, permission denials, crash proxies) grouped by change → session → tool [REQ: digest-subcommand-aggregates-error-signals]
- [x] 3.3 Record per-group first-seen / last-seen timestamps and a truncated (≤200 char) snippet of the most-recent occurrence [REQ: digest-subcommand-aggregates-error-signals]
- [x] 3.4 Implement `to_markdown(DigestResult) -> str` with sections `## Summary`, `## Errors by change`, `## Crash suspects` [REQ: digest-subcommand-aggregates-error-signals]
- [x] 3.5 Implement `to_json(DigestResult) -> dict` for `--json` output [REQ: digest-subcommand-aggregates-error-signals]
- [x] 3.6 Unit tests: bash exit rows appear, max_tokens stop counted, clean session produces no noise, grouping by change works across worktree dirs [REQ: digest-subcommand-aggregates-error-signals]

## 4. Session timeline

- [x] 4.1 Implement `lib/set_orch/forensics/timeline.py::session_timeline(resolved, uuid_or_prefix, *, errors_only=False, tool=None) -> Timeline` [REQ: session-subcommand-shows-targeted-timeline]
- [x] 4.2 Resolve session UUID by prefix across all resolved session dirs; minimum prefix length 6; ambiguous prefix raises `AmbiguousSessionPrefix` with candidate list [REQ: session-subcommand-shows-targeted-timeline]
- [x] 4.3 Build timeline entries: `Timestamp`, `EventType`, `ToolName?`, `Outcome`, `Summary` [REQ: session-subcommand-shows-targeted-timeline]
- [x] 4.4 Implement `--errors-only` filter and `--tool <name>` filter [REQ: session-subcommand-shows-targeted-timeline]
- [x] 4.5 Implement markdown + JSON output [REQ: session-subcommand-shows-targeted-timeline]
- [x] 4.6 Unit tests: prefix resolution, ambiguous prefix, errors-only filter, tool filter [REQ: session-subcommand-shows-targeted-timeline]

## 5. Content-only grep

- [x] 5.1 Implement `lib/set_orch/forensics/grep.py::grep_content(resolved, pattern, *, tool=None, limit=50, case_insensitive=False) -> list[GrepMatch]` [REQ: grep-subcommand-emits-content-only-matches]
- [x] 5.2 Parse each jsonl line, extract `message.content` text, apply regex to that (NOT the raw line), emit header `<change>/<short-uuid> @ <timestamp>:` + text region [REQ: grep-subcommand-emits-content-only-matches]
- [x] 5.3 Include ≤2 lines of surrounding context around each match [REQ: grep-subcommand-emits-content-only-matches]
- [x] 5.4 Enforce `--limit` cap (default 50) and print trailer `(N more matches suppressed; use --limit to raise)` when truncated [REQ: grep-subcommand-emits-content-only-matches]
- [x] 5.5 Unit tests: jsonl structural keys never appear in output, limit cap enforced with trailer, case-insensitive flag works, tool filter works [REQ: grep-subcommand-emits-content-only-matches]

## 6. Orchestration summary

- [x] 6.1 Implement `lib/set_orch/forensics/orchestration.py::orchestration_summary(resolved) -> OrchestrationSummary` [REQ: orchestration-subcommand-summarises-orch-level-logs]
- [x] 6.2 Parse `orchestration-events.jsonl` to build dispatch table (per-change: first_dispatch_at, num_dispatches, last_gate_status, terminal_status) [REQ: orchestration-subcommand-summarises-orch-level-logs]
- [x] 6.3 Parse `orchestration-events.jsonl` to build gate-outcome counts grouped by gate name (pass/fail/skipped/cached) [REQ: orchestration-subcommand-summarises-orch-level-logs]
- [x] 6.4 Parse `orchestration-state-events.jsonl` to produce ordered state-transition timeline [REQ: orchestration-subcommand-summarises-orch-level-logs]
- [x] 6.5 Extract terminal status line (timestamp of `all_done` event or last state event if missing) [REQ: orchestration-subcommand-summarises-orch-level-logs]
- [x] 6.6 Exit non-zero with clear error when `resolved.orchestration_dir is None` [REQ: orchestration-subcommand-summarises-orch-level-logs]
- [x] 6.7 Implement markdown + JSON output [REQ: orchestration-subcommand-summarises-orch-level-logs]
- [x] 6.8 Unit tests with fixture orchestration-events.jsonl: dispatch counts, gate outcome grouping, missing orchestration dir error path [REQ: orchestration-subcommand-summarises-orch-level-logs]

## 7. Discover subcommand

- [x] 7.1 Implement discover renderer in `lib/set_orch/forensics/discover.py` that walks `ResolvedRun` and computes jsonl count + total size + most-recent mtime per session dir [REQ: discover-subcommand-lists-resolved-sources]
- [x] 7.2 For the orchestration dir, emit a per-artifact presence list: `orchestration-events.jsonl`, `orchestration-state-events.jsonl`, `orchestration-plan.json`, `orchestration-state.json`, `journals/`, `messages/` with `(found)` / `(missing)` markers (never omit missing) [REQ: discover-subcommand-lists-resolved-sources]
- [x] 7.3 Markdown output: one table for session dirs + one section for orchestration artifacts [REQ: discover-subcommand-lists-resolved-sources]
- [x] 7.4 JSON output with top-level keys `run_id`, `main`, `worktrees`, `orchestration` [REQ: discover-subcommand-lists-resolved-sources]
- [x] 7.5 Unit tests: 2-worktree run produces 3-row table, JSON shape is valid + stable [REQ: discover-subcommand-lists-resolved-sources]

## 8. CLI entry point

- [x] 8.1 Create `bin/set-run-logs` (Python, executable, `#!/usr/bin/env python3`) — thin argparse/Click wrapper calling `lib.set_orch.forensics` [REQ: resolve-all-session-dirs-for-a-run-id]
- [x] 8.2 Subcommand `discover` wired to `discover` renderer; supports `--json` [REQ: discover-subcommand-lists-resolved-sources]
- [x] 8.3 Subcommand `digest` wired to `digest_run`; supports `--json` [REQ: digest-subcommand-aggregates-error-signals]
- [x] 8.4 Subcommand `session <uuid>` wired to `session_timeline`; supports `--errors-only`, `--tool <name>`, `--json`; non-zero exit on ambiguous prefix [REQ: session-subcommand-shows-targeted-timeline]
- [x] 8.5 Subcommand `grep <pattern>` wired to `grep_content`; supports `-i`, `--tool <name>`, `--limit <N>` [REQ: grep-subcommand-emits-content-only-matches]
- [x] 8.6 Subcommand `orchestration` wired to `orchestration_summary`; supports `--json`; non-zero exit when orchestration dir is missing [REQ: orchestration-subcommand-summarises-orch-level-logs]
- [x] 8.7 Register `set-run-logs` in `pyproject.toml` `[project.scripts]` so `pip install -e .` makes it callable [REQ: resolve-all-session-dirs-for-a-run-id]
- [x] 8.8 Smoke test: run each subcommand against a real recent run dir and verify exit codes + output shape [REQ: resolve-all-session-dirs-for-a-run-id]

## 9. Skill `/set:forensics`

- [x] 9.1 Create `.claude/skills/set/forensics/SKILL.md` with frontmatter (name, description, tags) matching the `/set:help` / `/set:audit` style [REQ: skill-set-forensics-teaches-triage-flow]
- [x] 9.2 Document the triage order: discover → digest → session --errors-only → grep → orchestration cross-ref → raw jsonl as last resort [REQ: skill-set-forensics-teaches-triage-flow]
- [x] 9.3 Include an explicit warning against reading raw session jsonl files unbounded (300+ KB each) [REQ: skill-set-forensics-teaches-triage-flow]
- [x] 9.4 Keep skill under 200 lines; procedural style, command-focused, no narrative prose [REQ: skill-set-forensics-teaches-triage-flow]

## 10. Discoverability wiring

- [x] 10.1 Add a row to `.claude/rules/capability-guide.md` in the command table for `/set:forensics` with description "Post-run debugging / error triage" [REQ: skill-set-forensics-teaches-triage-flow]
- [x] 10.2 Add a mention of `/set:forensics` to the `/set:help` skill output (find the help skill's content file under `.claude/skills/set/help/` and add a one-line reference) [REQ: skill-set-forensics-teaches-triage-flow]
- [x] 10.3 Add `set-run-logs` to the CLI Tools table in `capability-guide.md` with purpose "Forensic analysis of completed orchestration run" [REQ: resolve-all-session-dirs-for-a-run-id]

## 11. Consumer deployment

- [x] 11.1 Verify `bin/set-run-logs` is picked up by `set-project init`'s binary deploy path (or add it if binaries are whitelisted) so consumer projects can run the CLI against their own runs [REQ: resolve-all-session-dirs-for-a-run-id]
- [x] 11.2 Verify the skill file under `.claude/skills/set/forensics/` is deployed by `set-project init` (skills follow the existing deploy pattern) [REQ: skill-set-forensics-teaches-triage-flow]
- [x] 11.3 Manual smoke: run `set-project init` against a scratch dir and confirm both CLI and skill appear [REQ: skill-set-forensics-teaches-triage-flow]

## Acceptance Criteria (from spec scenarios)

### Resolve-all-session-dirs-for-a-run-id

- [x] AC-1: WHEN `set-run-logs discover craftbrew-run-20260421-0025` is invoked and `~/.claude/projects/` contains the main dir and two `-wt-*` worktree dirs for that run THEN the CLI reports the main session dir and both worktree session dirs keyed by their change name AND reports the orchestration dir at `~/.local/share/set-core/e2e-runs/craftbrew-run-20260421-0025/` [REQ: resolve-all-session-dirs-for-a-run-id, scenario: main-run-plus-worktrees-resolved]
- [x] AC-2: WHEN another run with a name-collision suffix exists alongside the target run THEN the CLI distinguishes exact-run dirs from name-collision neighbours by requiring the character after the run id to be end-of-string or `-` AND does not include the collision dir in resolution [REQ: resolve-all-session-dirs-for-a-run-id, scenario: unrelated-runs-not-picked-up-by-prefix]
- [x] AC-3: WHEN the orchestration run dir is missing but session dirs exist THEN the CLI resolves session dirs, sets `orchestration_dir=None`, emits a WARNING on stderr naming the missing path AND `discover` / `digest` / `session` / `grep` still work AND `orchestration` subcommand exits non-zero with a clear error [REQ: resolve-all-session-dirs-for-a-run-id, scenario: orchestration-dir-missing]

### Discover-subcommand-lists-resolved-sources

- [x] AC-4: WHEN `discover` is invoked on a two-worktree run THEN output contains a markdown table with 3 rows (main + 2 worktrees) AND a separate section listing orchestration artifacts with `(found)` / `(missing)` markers [REQ: discover-subcommand-lists-resolved-sources, scenario: markdown-output-for-a-two-worktree-run]
- [x] AC-5: WHEN `discover --json` is invoked THEN output is valid JSON parseable by `json.loads` AND contains top-level keys `run_id`, `main`, `worktrees`, `orchestration` [REQ: discover-subcommand-lists-resolved-sources, scenario: json-output-shape-is-stable]

### Digest-subcommand-aggregates-error-signals

- [x] AC-6: WHEN a session contains a Bash `tool_result` with content `"exit code: 1\nnpm install failed"` THEN the digest includes a row under the session's change listing `Bash` as the tool, count ≥1, and the snippet truncated to 200 chars [REQ: digest-subcommand-aggregates-error-signals, scenario: bash-exit-codes-surface-in-digest]
- [x] AC-7: WHEN a session's last assistant message has `stop_reason: "max_tokens"` THEN the digest's `## Crash suspects` or `## Errors by change` section includes that session's UUID with reason `max_tokens` [REQ: digest-subcommand-aggregates-error-signals, scenario: max-tokens-stop-reason-counted]
- [x] AC-8: WHEN a session has only successful tool calls and final `stop_reason: "end_turn"` THEN the digest does NOT list that session under any error subsection [REQ: digest-subcommand-aggregates-error-signals, scenario: clean-session-produces-no-noise]

### Session-subcommand-shows-targeted-timeline

- [x] AC-9: WHEN the run has a session `0797d182-...` AND `session 0797d1` is invoked THEN the CLI resolves the prefix and emits that session's timeline [REQ: session-subcommand-shows-targeted-timeline, scenario: session-found-by-prefix]
- [x] AC-10: WHEN two sessions share a 4-char prefix AND the user passes a matching prefix THEN the CLI exits non-zero and lists the full UUIDs of the matching sessions AND does not emit any timeline [REQ: session-subcommand-shows-targeted-timeline, scenario: ambiguous-prefix-reports-candidates]
- [x] AC-11: WHEN a session has 50 tool calls of which 3 errored AND `--errors-only` is passed THEN output lists only the 3 error entries plus any anomalous stop [REQ: session-subcommand-shows-targeted-timeline, scenario: errors-only-filters-cleanly]

### Grep-subcommand-emits-content-only-matches

- [x] AC-12: WHEN the user searches for `"EACCES"` AND the match occurs inside a Bash tool result THEN output does NOT contain jsonl keys like `"type":"tool_result"` or `"tool_use_id":"..."` AND contains only extracted text content around the match [REQ: grep-subcommand-emits-content-only-matches, scenario: grep-extracts-message-content-not-jsonl-line]
- [x] AC-13: WHEN a pattern matches 5000 times AND no `--limit` is passed THEN the CLI emits at most 50 matches (default cap) and prints trailer `(4950 more matches suppressed; use --limit to raise)` [REQ: grep-subcommand-emits-content-only-matches, scenario: limit-cap-prevents-context-blowout]

### Orchestration-subcommand-summarises-orch-level-logs

- [x] AC-14: WHEN a change was dispatched 3 times across the run THEN its `num_dispatches` column is `3` [REQ: orchestration-subcommand-summarises-orch-level-logs, scenario: dispatch-counts-reflect-all-dispatch-events]
- [x] AC-15: WHEN the log contains 5 `VERIFY_GATE` events for `review` (3 pass, 2 fail) and 2 for `build` (both pass) THEN the summary shows `review: pass=3, fail=2` and `build: pass=2` [REQ: orchestration-subcommand-summarises-orch-level-logs, scenario: gate-outcomes-grouped-by-gate-name]

### Skill-set-forensics-teaches-triage-flow

- [x] AC-16: WHEN `.claude/rules/capability-guide.md` is read THEN the command table includes a row for `/set:forensics` with a brief description and a "When" entry like "Post-run debugging / error triage" [REQ: skill-set-forensics-teaches-triage-flow, scenario: skill-registered-in-capability-guide]
- [x] AC-17: WHEN the user invokes `/set:help` THEN the quick-reference output mentions `/set:forensics` as a debugging entry-point [REQ: skill-set-forensics-teaches-triage-flow, scenario: skill-listed-in-set-help]
