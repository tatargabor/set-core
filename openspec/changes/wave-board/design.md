## Context

A wave board answers one question about a running job: where is it, item by item. Three
layers update it, in falling order of reliability:

1. **The job file** (`docs/waveboard/<job>.json`, tracked) — the registration: waves, items,
   and for each item the evidence that proves it.
2. **The hook-run sync** — derives status from that evidence on every Stop, whether or not
   the agent remembered anything.
3. **The agent's own report** (`set-wave-board set`) — the fast lane, overwritten by evidence
   wherever evidence speaks.

The board itself is an Artifact page reading its own database. Only the agent can write that
database, through its `ArtifactData` tool, so the script cannot close the loop by itself.

## Goals / Non-Goals

**Goals:** deterministic status from evidence; usable in every project set-core deploys to;
macOS and Linux; several machines and people cloning to different paths; a push that happens
even when the agent forgets.

**Non-Goals:** writing the database from a script; a board anyone edits from the page;
product-roadmap concepts (dates, owners, estimates).

## Decisions

### D1. The script computes, the hook asks, the agent pushes

`sync` writes the exact document body to `.set/waveboard/<job>.state.json`, and the agent
sends it with `ArtifactData set … file_path=<that file>`. The payload is a file, not inline
data, so the agent never retypes the board and cannot alter it on the way. The Stop hook is
what makes the push reliable: it turns "a payload differs from what was pushed" into a
`decision: block` whose reason is the complete procedure, so a session that forgot the board
is told, at the moment it stops, exactly what to send.

*Alternative rejected:* a background process pushing through an API. There is none a script
may call; the database is reachable through the agent only.

### D2. Absence of evidence is not a verdict

`path-exists` and `commit` yield `done` or nothing; `openspec-tasks` yields a status only when
the tasks file (or its archive) exists. A missing path cannot distinguish "not done yet" from
"not on this machine" or "not pulled yet", and the cross-machine requirement makes the second
case ordinary. Reporting it as `todo` would revert a correct status the next time a session
ran on a stale clone. Where evidence does speak it wins, including over a fast-lane `done` —
that is the case the evidence layer exists for.

### D3. Blocked and skipped are human decisions

No evidence type can observe "we decided not to" or "waiting on someone", so a manual
`blocked` or `skipped` survives every sync. Every other manual status is a claim evidence can
check, and it is checked.

### D4. Cross-project evidence by registry name only

A job that spans projects names them as the set-core registry does. The path is resolved per
machine at sync time (`SET_CORE_REGISTRY` overrides the registry file, which also makes it
testable). An unregistered name is reported, not guessed: the item keeps its status. Nesting
`project` inside `project` is refused — it would only re-resolve a name.

### D5. Content hash, not timestamps, decides a push

`content_hash` is SHA-256 over the canonical JSON of `{schema, job, title, waves}`.
`synced_at` and `synced_by` are deliberately outside it: a sync that found nothing new must not
produce a push, or the hook would ask for one on every stop. The payload file is rewritten
only when the hash changes, so `synced_at` reads "when the state last changed", which is the
fact a reader of the board wants.

### D6. What was pushed is machine-local

`.set/waveboard/<job>.pushed.json` records `{hash, version, pushed_at}` on this machine only.
Another machine has no record, sees the job as pending, and is reminded; if that person cannot
write the Artifact (only the owner and invited editors can), the push fails and the hook backs
off for 30 minutes per job. `SET_WAVEBOARD_PUSH=off` silences it entirely. Committing the
pushed record instead would turn every push into a commit and make two machines fight over it.

The version recorded is the database document's `version`, which every write must pin with
`if_version`. With no record the agent omits it (creating the document); if the document
already exists the write is refused, and the procedure says to `get` it and redo with the
version it shows.

### D7. The tool keeps its own state out of git

`.set/` is gitignored in every set-core consumer, but a project initialised by hand may not
be. The tool writes `.set/waveboard/.gitignore` containing `*`, so its machine-local files never
show up as untracked whatever the project's own ignore file says.

### D8. One Stop hook, one subprocess, no network

`set-hook-waveboard` is a small Python script that calls `set-wave-board` (resolved next to
its own real path, then `PATH`) with a timeout well inside the hook's own. Sync reads files and
runs `git log`; nothing touches the network. Every early exit is silent and exits 0, because a
Stop hook that errors is noise on every turn of every session in the project.

### D9. Deployment: extend the canonical check, keep the additive merge

`set-deploy-hooks` merges by matcher, then by command, and never removes a project's hook.
Adding the waveboard hook to the Stop entry is therefore safe; the gap is the early return,
which treats "base hooks present" as canonical and would never deliver a new hook to an
existing project. The check now also requires `set-hook-waveboard` in some Stop entry.

### D10. The page is the template; render embeds a seed

`templates/waveboard/page.html` is skeleton-less, as an Artifact page is. It reads the
database when `claude.use("db")` resolves and otherwise the embedded seed. `render` fills the
seed from the payload and, by default, wraps a document skeleton so the file opens offline;
`--bare` leaves the skeleton off for publishing, which gives the published page a real first
frame before the database answers.

## Risks / Trade-offs

- **A machine without the new install has a hook it cannot run.** `set-project init` writes
  the command name; the executable arrives with `install.sh`. Until it is re-run there, Claude
  Code reports a non-blocking hook error on that machine. Same exposure as every other
  `set-hook-*` command; the remedy is the same `install.sh` run.
- **Hostname in a tracked file.** `by` records the machine that changed an item, as asked. It
  is a short hostname, and `SET_WAVEBOARD_BY` overrides it for anyone who prefers a label.
- **A reminder per machine.** Two machines working the same job each get reminded. Accepted:
  the alternative is a shared pushed record, which D6 rejects.
