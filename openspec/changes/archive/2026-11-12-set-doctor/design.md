## Context

The checks this command needs mostly exist, scattered: `set-kb doctor --json` (per project, about
2 s), `sac doctor --json` (all projects at once, about 6.5 s), `sac relay status`, `set-glm
--check` (a live, paid model call), `gh auth status`. What does not exist is a check of the
install itself, of the checkout against its remote, of each project's deployed version and MCP
registration, and one place that runs them all and says what to do.

## Goals / Non-Goals

**Goals:** a developer, or the session helping them, runs one command and gets every set-core
problem on the machine with the command that fixes it. A calling tool gets the same as JSON.
The default run is fast enough to run after every setup step, and free.

**Non-Goals:** fixing anything (the doctor reports and never repairs); the consumer's own
environment (its doctor owns that); a project's code health (`set-audit`).

## Decisions

### D1 — Measure against the installer's own list

"Is set-core installed" is answered by parsing the `scripts=(…)` list from `install.sh` and
checking that each name in `~/.local/bin` resolves into THIS checkout. A hand-kept list in the
doctor would drift from the installer, which is the same two-copies defect the providers change
removed. A link into a different checkout is a `warn`: it works, but it runs other code.

### D2 — Deployed version, not a dry-run, by default

`set-project init --dry-run` measured 17.6 s on one project, so 70 projects would take about 20
minutes. Every deploy writes the set-core version to `<project>/.claude/.set-version`. Comparing
that version with this checkout (`rev-list --count`) answers "is this project behind" in
milliseconds. `--deep` adds the dry-run for whoever wants the file-level plan.

### D3 — One live MCP probe, against a throwaway repository

The MCP server is one program for all projects; what differs per project is its registration.
So the doctor checks every registration statically, in the Claude config (`~/.claude.json`,
`CLAUDE_CONFIG_DIR`-aware): present, the server directory is this checkout's, and
`CLAUDE_PROJECT_DIR` is the project itself. It speaks MCP once (stdio: `initialize`, then
`tools/call kb_search`) with `CLAUDE_PROJECT_DIR` pointing at a one-file repository in a temp dir.
Measured: the same call against a large real project took 67 s, all of it index refresh, which is
`set-kb doctor`'s question, not the server's.

### D4 — Status vocabulary and exit code

`ok`, `warn` (works, but something is behind or missing that a developer will hit later), `fail`
(a thing that is supposed to work does not), `skip` (not applicable or not measured, with the
reason; never reads as ok). Exit 1 on any `fail`, 0 otherwise. `--strict` also fails on `warn`.
A skipped check is never counted as passing, the same rule as "a gap is not a zero".

### D5 — A data repository is not a consumer

A registry entry with `"deploy": false` is not expected to carry deployed rules, MCP or bus
hooks. Those checks are `skip` there with that reason, and its path, git and `set-kb doctor`
are still checked, because consumers link to it.

### D6 — Secrets never reach the output

The provider check resolves the GLM plan in-process and reports only "credential present" and
the endpoint `describe()` already prints. `gh auth status` output is not relayed, only its exit
code and the account name. `--live` runs `set-glm --check` and relays only its verdict line.

### D7 — Per-project work runs in parallel

`set-kb doctor` per project is about 2 s. It runs in a thread pool (8 workers), so 70 projects
take about 20 s. `sac doctor` runs once for all of them.

## Risks / Trade-offs

- `git fetch` touches the network and updates remote-tracking refs. `--offline` skips it, and so
  does a 20 s timeout. Either way the ahead/behind line says it compared against refs that were
  not fetched.
- A project's `.set-version` can be a tag. Both sides are resolved to commits before counting.
