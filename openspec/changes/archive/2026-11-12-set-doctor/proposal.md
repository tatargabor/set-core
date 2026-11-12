## Why

A second developer is about to set up set-core on their own machine from a setup mail. Today
nothing tells them, or the person helping them, whether that machine is ready: whether the
installer ran, whether the checkout is current, whether each project got its rules, its MCP
server and its bus hooks, and whether search and the provider key work. Each of these has its
own tool (`set-kb doctor`, `sac doctor`, `set-glm --check`, `gh auth status`) or none at all,
and a failure in one shows up much later as something else: an agent with no `kb_search`, a
project that never hears the bus, a session that cannot start GLM.

Measured on this machine while scoping (2026-11-12): of 70 registered projects, 46 have the
set-core MCP server registered, and set-core's own registration points its
`CLAUDE_PROJECT_DIR` at a worktree instead of the project. Nothing reported either.

A sibling platform's own doctor will call this one for the set-core half, so the answer
also has to be machine-readable and versioned.

## What Changes

- A new command `set-doctor`, which checks the set-core side of a developer machine. Each check is
  one line, `ok` / `warn` / `fail` / `skip`, with the exact command that fixes it. It exits
  non-zero when any check fails. `--json` returns a versioned contract (`set-doctor/1`).
- Sections: the install (every command the installer ships is linked into this checkout, the link
  directory is on PATH, the MCP server's dependencies are installed); the checkout (dirty files,
  ahead/behind its upstream after a fetch); the tools (python ≥ 3.10, uv, node, jq, git, claude,
  the OpenSpec CLI at least the version the checkout's generated skills were made with); the MCP
  server (one live stdio probe: initialize and `kb_search` against a throwaway repository);
  every registered project (path, git repository, deploy flag, deployed set-core version against
  this checkout, the MCP registration and where it points, `set-kb doctor`, its bus wiring); the
  bus (`sac` launcher, relay reachable); the GLM provider (configured with a credential, never
  printed); GitHub CLI authentication.
- `set-kb doctor` gains a `linked` check: every project in `config.linked` resolves through the
  registry and loads.
- `--project <glob>` limits the per-project section, `--offline` skips the fetch and the relay,
  `--deep` adds `set-project init --dry-run` per project, and `--live` adds the paid provider
  probe (`set-glm --check`).

## Capabilities

### New Capabilities
- `machine-doctor`: the developer-machine check, its sections, its exit code and its JSON contract.

### Modified Capabilities
- `kb-search-access`: `set-kb doctor` reports whether every linked project can be searched.
  Added as a requirement in the `kb-linked-projects` change's capability.

## Impact

- New: `bin/set-doctor`, `lib/set_doctor/` (stdlib only), `tests/unit/test_set_doctor.py`.
- `install.sh`: `set-doctor` joins the installed commands.
- `lib/set_kb/cli.py`: the `linked` doctor check.
- `docs/reference/set-doctor.md`.
- Nothing is written by the doctor except the throwaway probe repository in a temp dir. The fetch
  updates remote-tracking refs only.
