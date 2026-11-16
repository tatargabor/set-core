# Machine check — `set-doctor`

`set-doctor` answers one question: **is the set-core side of this developer machine in order?**
It reports every problem with the command that fixes it, and repairs nothing. Run it after
`./install.sh`, after `git pull`, and whenever an agent is missing a tool it should have.

```bash
set-doctor                 # text, grouped by section; projects with a problem are listed
set-doctor --all           # list every project, not only the ones with a problem
set-doctor --json          # the machine contract, schema "set-doctor/1"
set-doctor --project 'aiplus-*'   # only matching registry entries
set-doctor --offline       # no git fetch, no relay check
set-doctor --deep          # also `set-project init --dry-run` per project (about 17 s each)
set-doctor --live          # also one PAID model call through set-glm --check
set-doctor --strict        # exit 1 on warnings too
```

Exit code: **1 when any check is `fail`**, 0 otherwise (with `--strict`, also on `warn`).

## Statuses

| status | meaning |
|---|---|
| `ok` | measured and in order |
| `warn` | works, but something is behind or missing that will bite later |
| `fail` | something that should work does not |
| `skip` | not applicable or not measured, with the reason. **Never a pass.** |

Every `warn` and `fail` carries `fix`: the exact command to run.

## What it checks

| section | checks |
|---|---|
| install | every command in `install.sh`'s list is linked in `~/.local/bin` and resolves into **this** checkout (`warn` if it points into another one); `~/.local/bin` is on `PATH`; the MCP server's environment exists (`mcp-server/.venv`) |
| checkout | uncommitted files; ahead/behind the branch's upstream after a `git fetch` (20 s timeout; `--offline` compares with the refs on disk and says so) |
| tools | python3 ≥ 3.10, uv, node ≥ 18, jq, git, claude, and the OpenSpec CLI at least the version the checkout's generated OpenSpec skills were made with |
| mcp | one live MCP conversation: the server of this checkout is started over stdio, `initialize`, then `kb_search` against a throwaway one-file repository |
| bus | the `sac` launcher; `sac doctor` once for all projects; the relay's health endpoint |
| project | per registry entry: the path exists and is a git repository; the deployed set-core version (`.claude/.set-version`) against this checkout; the set-core MCP registration in the Claude config (present, this checkout's server, `CLAUDE_PROJECT_DIR` = the project); `set-kb doctor` (including whether every linked project resolves); the project's bus wiring. A `"deploy": false` entry (a data repository, see `set-project register`) skips deploy, MCP and bus. |
| providers | GLM resolves from `providers.json` with a credential. A file that exists but is refused (e.g. not mode 0600) is a `fail` with the reason, not "not configured". |
| github | `gh auth status` |

## Secrets

No output, text or JSON, contains a credential. The provider check reports only that a
credential is present and the endpoint. `gh auth status` is reduced to its exit code and the
account name. `--live` relays only whether the call answered.

## JSON

```json
{
  "schema": "set-doctor/1",
  "ok": false,
  "root": "/path/to/set-core",
  "head": "23e31273",
  "counts": {"ok": 168, "warn": 91, "fail": 22, "skip": 3},
  "checks": [
    {"section": "project", "name": "mcp", "status": "warn", "project": "<name>",
     "detail": "registered, but CLAUDE_PROJECT_DIR=<worktree>, not <project>",
     "fix": "cd <project> && claude mcp remove set-core; set-project init"}
  ]
}
```

`project` is present only on per-project records; `fix` only on `warn`/`fail`. A caller (e.g. a
platform's own doctor) should treat any unknown `schema` as a contract change.

## Cost

Measured on 2026-11-12 on a machine with 70 registered projects: about 30 s. `set-kb doctor`
runs in parallel (8 workers), `sac doctor` once, and the MCP probe takes about 1 s. `--deep`
adds about 17 s per project.
