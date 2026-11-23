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
| bus | the `sac` launcher (or the `sac` declaration's command); `sac doctor` once for all projects; the relay's health endpoint |
| project | per registry entry that is a git repository: the deployed set-core version (`.claude/.set-version`) against this checkout; the set-core MCP registration in the Claude config (present, this checkout's server, `CLAUDE_PROJECT_DIR` = the project); `set-kb doctor` (including whether every linked project resolves); the project's bus wiring (see below); every module doctor's records about that project. A `"deploy": false` entry (a data repository, see `set-project register`) skips deploy, MCP and bus. Entries whose path is gone or is not a git repository are reported together in ONE `stale` warn, each named with its reason, with a fix that deregisters exactly those — bookkeeping, so it does not set the exit code. |
| modules | every module doctor declared in `doctors.d` (below): its machine-level records, records about a path no registered project has, a declaration that is broken, duplicated, or names a command not installed on this machine |
| providers | GLM resolves from `providers.json` with a credential. A file that exists but is refused (e.g. not mode 0600) is a `fail` with the reason, not "not configured". |
| github | `gh auth status` |

## The bus rule

The `bus` record per project comes from `sac doctor`'s `hooks` and `live` fields:

| situation | status |
|---|---|
| a **live** seat, and no `session-start` or no `watch-guard` hook | `fail`, naming the seat(s) and the missing hook(s) |
| no hooks, no live seat | `warn` |
| hooks wired, no problem | `ok` |
| any other `sac doctor` problem (e.g. a machine path in a tracked settings file) | `warn` |
| a hook kind wired by more than one carrier (settings file **and** plugin) | an extra `bus wiring` `warn` naming the carriers — each carrier runs the hook |

Why the live case is a `fail`. Without `session-start`, the session never gets the instruction
to watch its inbox as a background shell. Without `watch-guard`, nothing declines a `Monitor`
watch, and every 30-minute `Monitor` expiry wakes the session to re-read its whole context. A
session measured in exactly this state did that ~26 times at ~230k tokens of context (B-193).

## Module doctors

`set-doctor` is the umbrella over the module doctors installed on this machine. A module
**declares** itself; nothing is hard-coded. Each declaration is one file in
`<set-core config dir>/doctors.d/` (`$SET_CONFIG_DIR`, else `$XDG_CONFIG_HOME/set-core`, else
`~/.config/set-core`), normally written by the module's own installer:

```json
{"module": "example", "command": ["example", "doctor", "--json"],
 "contract": "doctor/1", "install": "one line that installs it", "timeout_s": 120}
```

Each declared module runs **once** per `set-doctor` run, in parallel with the project checks.
Every record it produces carries `"module"`.

**The `doctor/1` contract** a module prints:

```json
{"schema": "doctor/1", "module": "example",
 "checks": [{"section": "x", "name": "thing", "status": "warn", "detail": "...",
             "fix": "the command", "path": "/abs/path/of/the/project"}]}
```

- A record with `path` lands on the registered project at the same real path. Without one, or
  with a path no project has, it is shown under MODULES.
- Statuses are the same four. An unknown `schema`, or a status outside the four, is a `fail` of
  that module, never a silent drop.
- A command that times out, or prints no parseable report, is a `fail` with its error tail.
- A declared command that is not on `PATH` is a `warn`, *declared but not installed on this
  machine*, with the declaration's `install` line as the fix. This is how a second developer's
  machine learns what it is missing.

**Contracts that predate `doctor/1`** are read through adapters:

| contract | module | notes |
|---|---|---|
| `sac.doctor/1` | `sac` | built in; runs even with no declaration. A declaration replaces its command (one run, never two). |
| `set-kb.doctor/1` | `set-kb` | built in, per project. `install.sh` writes its declaration. |
| `aiplus-doctor/1` | the family doctor | only when declared. Per-repository records join the registered project of the **same name**. Machine records and unknown repositories go under MODULES. Its own record about `set-doctor` is dropped, because it describes the run reading it. |

**No recursion.** Every module runs with `SET_DOCTOR_CHILD=1`. A `set-doctor` started under that
marker runs no module doctors and says so with one `skip`, so a module doctor that itself calls
`set-doctor` is safe to declare.

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

`project` is present only on per-project records, `module` only on records a module doctor produced, `fix` only on `warn`/`fail`. A caller (e.g. a
platform's own doctor) should treat any unknown `schema` as a contract change.

## Cost

Measured on 2026-11-12 on a machine with 70 registered projects: about 30 s. `set-kb doctor`
runs in parallel (8 workers), `sac doctor` once, and the MCP probe takes about 1 s. `--deep`
adds about 17 s per project.
