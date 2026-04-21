## ADDED Requirements

## IN SCOPE
- CLI `set-run-logs <run-id>` with subcommands `discover`, `digest`, `session`, `grep`, `orchestration`.
- Automatic resolution of all Claude Code session transcript directories belonging to a run (main run dir + every `-wt-<change>` worktree session dir under `~/.claude/projects/`).
- Automatic resolution of orchestration-level log artifacts under `~/.local/share/set-core/e2e-runs/<run-id>/`.
- Aggregated error/anomaly digest across all session jsonls (tool errors, non-zero bash exits, stop-reason anomalies, user interrupts, permission denials, agent crashes).
- Targeted single-session view with tool-call timeline and error-only filter.
- Content-only grep over jsonl bodies that emits matching `message.content` text (not the full jsonl line).
- Orchestration event summary (dispatches, gate outcomes, state transitions, terminal statuses).
- Skill `/set:forensics` at `.claude/skills/set/forensics/SKILL.md` that teaches the standard triage flow.
- Registration of the skill in `.claude/rules/capability-guide.md` and in the `/set:help` quick reference.

## OUT OF SCOPE
- Writing any new files into the run dir or session dirs (forensics is read-only).
- Modifying Claude Code session jsonl format or how the harness writes transcripts.
- Cross-run comparison (belongs to the separate `set-compare` tool).
- Live tailing of an in-flight run (this tool targets completed runs; live monitoring is the sentinel's job).
- Consumer-scaffold or project-type-specific signals. The CLI runs against ANY run regardless of project type.
- Automatic root-cause LLM analysis. The CLI only surfaces filtered data; reasoning stays with the caller (agent or human).

### Requirement: Resolve all session dirs for a run id
The `set-run-logs` CLI SHALL, given a `<run-id>` argument, resolve the complete set of Claude Code session directories that belong to that run.

The resolution algorithm SHALL:
1. Construct the expected base path prefix for the main run: the encoded form of `~/.local/share/set-core/e2e-runs/<run-id>` as used by Claude Code under `~/.claude/projects/`.
2. Enumerate all directories under `~/.claude/projects/` whose names START WITH that encoded base prefix. This captures the main dir PLUS every `-wt-<change>` worktree dir for that run.
3. Also resolve the orchestration run dir at `~/.local/share/set-core/e2e-runs/<run-id>/`. If it does not exist, emit a warning but continue — the session dirs alone are still useful for forensics.
4. Emit a structured `ResolvedRun` value containing: `run_id`, `main_session_dir`, `worktree_session_dirs: dict[str, Path]` (change-name → dir), `orchestration_dir: Path | None`.

The encoding used by Claude Code replaces path separators with `-` and prepends `-home-tg-` (or the equivalent user-home prefix). Implementations SHALL reuse the `claude projects` encoding helper rather than re-deriving it, so changes to the harness are picked up automatically.

#### Scenario: Main run plus worktrees resolved
- **WHEN** `set-run-logs discover craftbrew-run-20260421-0025` is invoked
- **AND** `~/.claude/projects/` contains `-home-tg--local-share-set-core-e2e-runs-craftbrew-run-20260421-0025`, `-home-tg--local-share-set-core-e2e-runs-craftbrew-run-20260421-0025-wt-auth-core-and-admin-shell`, and `-home-tg--local-share-set-core-e2e-runs-craftbrew-run-20260421-0025-wt-stories-public`
- **THEN** the CLI SHALL report the main session dir and two worktree session dirs (keyed by `auth-core-and-admin-shell` and `stories-public`)
- **AND** SHALL report the orchestration dir at `~/.local/share/set-core/e2e-runs/craftbrew-run-20260421-0025/`

#### Scenario: Unrelated runs not picked up by prefix
- **WHEN** another run `craftbrew-run-20260421-0025x` exists in `~/.claude/projects/` alongside the target run
- **THEN** the CLI SHALL distinguish between exact-run dirs and name-collision neighbours by requiring the character immediately following the run id to be either the end-of-string or a `-` (the worktree separator)
- **AND** SHALL NOT include `craftbrew-run-20260421-0025x` in the resolution

#### Scenario: Orchestration dir missing
- **WHEN** `~/.local/share/set-core/e2e-runs/<run-id>/` does not exist but session dirs do
- **THEN** the CLI SHALL still resolve the session dirs, set `orchestration_dir=None`, and emit a `WARNING` on stderr naming the missing path
- **AND** the `discover` / `digest` / `session` / `grep` subcommands SHALL still work against the session dirs
- **AND** the `orchestration` subcommand SHALL exit with a clear error message when `orchestration_dir is None`

### Requirement: discover subcommand lists resolved sources
`set-run-logs <run-id> discover` SHALL emit a compact listing of every resolved source without reading any file content.

Output SHALL include, for each session dir:
- The change name (or `main` for the non-worktree dir)
- The absolute dir path
- The number of `*.jsonl` files in the dir
- The total byte size of the jsonl files (human-readable, e.g. `2.3 MB`)
- The most-recent jsonl's mtime

And for the orchestration dir (when present):
- The dir path
- A list of the known artifacts that exist: `orchestration-events.jsonl`, `orchestration-state-events.jsonl`, `orchestration-plan.json`, `orchestration-state.json`, `journals/`, `messages/`. Missing ones SHALL be shown as `(missing)` rather than omitted, so the caller can see gaps.

Default output format is markdown. `--json` SHALL emit a JSON object with the same data so callers can pipe to `jq`.

#### Scenario: Markdown output for a two-worktree run
- **WHEN** `set-run-logs <run-id> discover` is invoked
- **AND** there is one main session dir and two worktree dirs
- **THEN** the output SHALL contain one markdown table with 3 rows (main + 2 worktrees)
- **AND** a separate section listing orchestration artifacts with `(found)` / `(missing)` indicators

#### Scenario: JSON output shape is stable
- **WHEN** `set-run-logs <run-id> discover --json` is invoked
- **THEN** the output SHALL be valid JSON parseable by `json.loads`
- **AND** SHALL contain top-level keys `run_id`, `main`, `worktrees`, `orchestration`

### Requirement: digest subcommand aggregates error signals
`set-run-logs <run-id> digest` SHALL scan every jsonl line in every resolved session dir and aggregate the following signals:

1. **Tool-use errors** — any `tool_result` entry whose content has `is_error: true`, or any `tool_use` followed by a `tool_result` containing an `Error:` / `error:` prefix.
2. **Non-zero Bash exits** — any Bash tool result whose content includes `exit code: <nonzero>` OR whose JSON contains `exitCode != 0`.
3. **Stop-reason anomalies** — any assistant message whose final `stop_reason` is one of `max_tokens`, `tool_use_error`, `refusal`, or any non-`end_turn`/`tool_use`/`stop_sequence` value.
4. **User interrupts** — any message whose type indicates an explicit user abort (e.g. `"type": "user"` with `"isInterrupt": true`, or Claude Code's interrupt marker if present).
5. **Permission denials** — any assistant or system message mentioning `"permission"` combined with `"denied"` / `"not allowed"`.
6. **Agent crashes** — any session jsonl that ends without an `end_turn` or `tool_use` stop reason on the last assistant message (proxy for process death).

Aggregation SHALL group by `change → session_uuid → tool_name` (for tool-level signals) and `change → session_uuid` (for stop-reason / crash signals). Each group SHALL include:
- A count of occurrences
- The first-seen and last-seen timestamps (from jsonl line timestamps, which Claude Code always includes)
- A short text snippet (≤200 chars) of the most-recent occurrence's content, for scent

Default output format is markdown with the following structure:
- `## Summary` — total sessions scanned, total error signals, per-change counts
- `## Errors by change` — one `### <change>` subsection per change, with per-session bullet points
- `## Crash suspects` — sessions that ended without a clean `stop_reason`

`--json` SHALL emit the raw aggregation for programmatic consumption.

Performance: the digest SHALL stream jsonl files line-by-line (no full-file load) and SHALL complete in under 30 seconds for a run with 50 session files averaging 200 KB each.

#### Scenario: Bash exit codes surface in digest
- **WHEN** a session contains a `tool_result` for a Bash tool call whose content is `"exit code: 1\nnpm install failed"`
- **THEN** the digest SHALL include a row under the session's change listing `Bash` as the tool, count ≥1, and the snippet `"exit code: 1\nnpm install failed"` truncated to 200 chars

#### Scenario: max_tokens stop reason counted
- **WHEN** a session's last assistant message has `stop_reason: "max_tokens"`
- **THEN** the digest `## Crash suspects` or `## Errors by change` section SHALL include that session's UUID with reason `max_tokens`

#### Scenario: Clean session produces no noise
- **WHEN** a session has only successful tool calls and a final `stop_reason: "end_turn"`
- **THEN** the digest SHALL NOT list that session under any error subsection

### Requirement: session subcommand shows targeted timeline
`set-run-logs <run-id> session <uuid>` SHALL emit a compact timeline of a single session's tool calls and stop reasons.

The session UUID MAY be a full UUID or a unique prefix (minimum 6 chars). If the prefix is ambiguous across the run's session dirs, the CLI SHALL list the matches and exit non-zero.

Output SHALL include for each entry:
- Timestamp (ISO 8601)
- Event type: `tool_use`, `tool_result`, `stop`, `user_message`, `system_message`
- Tool name (when applicable)
- Outcome indicator: `ok` / `error` / `timeout`
- One-line summary (≤120 chars)

`--errors-only` SHALL filter to entries where the outcome is `error` or `timeout`, plus any `stop` entries with anomalous reasons.

`--tool <name>` SHALL filter to entries for the given tool name (e.g. `Bash`, `Edit`, `Read`).

Default output is markdown; `--json` emits the raw timeline.

#### Scenario: Session found by prefix
- **WHEN** the run has a session `0797d182-504e-4a72-8b44-b4ea129189bf`
- **AND** `set-run-logs <run-id> session 0797d1` is invoked
- **THEN** the CLI SHALL resolve the prefix to that session and emit its timeline

#### Scenario: Ambiguous prefix reports candidates
- **WHEN** two sessions share a 4-char prefix and the user passes a prefix matching both
- **THEN** the CLI SHALL exit non-zero and list the full UUIDs of the matching sessions
- **AND** SHALL NOT emit any timeline

#### Scenario: errors-only filters cleanly
- **WHEN** a session has 50 tool calls of which 3 errored
- **AND** `--errors-only` is passed
- **THEN** the output SHALL list only the 3 error entries plus any anomalous stop

### Requirement: grep subcommand emits content-only matches
`set-run-logs <run-id> grep <pattern>` SHALL regex-scan every jsonl across resolved session dirs and emit ONLY the matching `message.content` text, not the raw jsonl line.

For each match, output SHALL include:
- A header line: `<change>/<session-short-uuid> @ <timestamp>` followed by `:`
- The extracted text content, trimmed to the match region with ≤2 lines of surrounding context

`--tool <name>` SHALL restrict scanning to messages whose role/type indicates the given tool.

`--limit <N>` SHALL cap output at N matches (default 50) to protect agent context.

The regex SHALL be compiled with `re.MULTILINE`. Case-insensitive matching SHALL be available via `-i`.

#### Scenario: Grep extracts message content, not jsonl line
- **WHEN** the user searches for `"EACCES"` and a match occurs inside a Bash tool result
- **THEN** the output SHALL NOT contain jsonl keys like `"type":"tool_result"` or `"tool_use_id":"..."`
- **AND** SHALL contain only the extracted text content around the match

#### Scenario: Limit cap prevents context blowout
- **WHEN** a pattern matches 5000 times across the run
- **AND** no `--limit` is passed
- **THEN** the CLI SHALL emit at most 50 matches (default cap) and print a trailer `(4950 more matches suppressed; use --limit to raise)`

### Requirement: orchestration subcommand summarises orch-level logs
`set-run-logs <run-id> orchestration` SHALL summarise the orchestration-level log files under `~/.local/share/set-core/e2e-runs/<run-id>/`.

Output SHALL include:
- A dispatch table: one row per change with columns `change`, `first_dispatch_at`, `last_gate_status`, `terminal_status`, `num_dispatches`.
- A gate-outcome summary: counts of each `VERIFY_GATE` verdict (`pass`, `fail`, `skipped`, `cached`) grouped by gate name.
- A state-transition timeline: ordered list of state mutations from `orchestration-state-events.jsonl` (change, field, old → new).
- A terminal status line: time of `all_done` event if present, otherwise last known state timestamp.

When the orchestration dir is missing (per the resolve requirement), this subcommand SHALL exit non-zero with a clear error rather than silently returning empty.

Default output is markdown; `--json` emits the raw summary.

#### Scenario: Dispatch counts reflect all dispatch events
- **WHEN** a change was dispatched 3 times across the run
- **THEN** its `num_dispatches` column SHALL be `3`

#### Scenario: Gate outcomes grouped by gate name
- **WHEN** the log contains 5 `VERIFY_GATE` events for `review` (3 pass, 2 fail) and 2 for `build` (both pass)
- **THEN** the summary SHALL show `review: pass=3, fail=2` and `build: pass=2`

### Requirement: Skill /set:forensics teaches triage flow
The skill at `.claude/skills/set/forensics/SKILL.md` SHALL instruct an agent to follow this triage order when debugging a completed run:

1. Run `set-run-logs <run-id> discover` to confirm the scope of resolved sources.
2. Run `set-run-logs <run-id> digest` to get the error map.
3. For each suspect session in the digest, run `set-run-logs <run-id> session <uuid> --errors-only` BEFORE reading any raw jsonl.
4. Use `set-run-logs <run-id> grep <pattern>` for targeted probes (e.g. a specific error message signature).
5. Cross-reference with `set-run-logs <run-id> orchestration` for timing context (when the suspect session dispatched, which gate triggered it, what the terminal status was).
6. Only after exhausting the CLI's filtered views, fall back to reading raw jsonl with `Read` limited to specific line ranges.

The skill SHALL be under 200 lines and SHALL mirror the procedural style of `/set:help` / `/set:audit` (short, command-focused, no narrative prose).

The skill SHALL explicitly warn against reading raw session jsonl files unbounded — each file can be 300+ KB and will blow the context window.

#### Scenario: Skill registered in capability guide
- **WHEN** `.claude/rules/capability-guide.md` is read
- **THEN** the command table SHALL include a row for `/set:forensics` with a brief description and a "When" column entry like "Post-run debugging / error triage"

#### Scenario: Skill listed in /set:help
- **WHEN** the user invokes `/set:help`
- **THEN** the quick-reference output SHALL mention `/set:forensics` as a debugging entry-point
