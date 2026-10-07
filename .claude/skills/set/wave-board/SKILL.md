---
name: set:wave-board
description: Live execution status of a multi-step job that runs in waves — a cleanup across ten projects, a migration done one group at a time, any job with more steps than one session holds. Use it to create the job's board (a tracked job file plus a private claude.ai Artifact page), to report a finished step, and to push the board when the Stop hook asks for it. Trigger words - wave board, hullámtábla, waves, process roadmap, "where is the job", multi-project cleanup, rollout status, `set-wave-board`, a Stop-hook reminder that names a wave board.
---

# Wave board — `set-wave-board`

A **process roadmap**, not a product roadmap: which wave a job is in, which item is done, in
progress or blocked, and what is left. One job is one tracked file,
`docs/waveboard/<job>.json`, in the repository that runs the job, and one private Artifact page
that shows it live.

## When to use it

Use a board when a job has **several steps that outlive one session** or run across several
projects: the status must survive a compact, a `/clear`, a second machine and a second person.
A three-step task done in one sitting does not need one; a todo list is enough there.

## How the status stays true — three layers

1. **The job file** — waves, items, and for each item the **evidence** that proves it.
2. **`sync`**, run by the `set-hook-waveboard` Stop hook on every stop, whether or not you
   remembered — it derives status from evidence.
3. **Your own report**, `set-wave-board set <job> <item> <status>` — the **fast lane**. Report
   every finished step with it, straight away. But evidence and the hook are the guarantee:
   where evidence speaks it overrides your report (a `done` with unchecked task boxes comes
   back as `doing`, and `set` says so). Only `blocked` and `skipped` survive evidence — they
   are human decisions.

Give every item evidence wherever one exists. An item without evidence is only as reliable as
the last report.

| Evidence | Done when |
|---|---|
| `{"type":"openspec-tasks","path":"openspec/changes/<x>/tasks.md"}` | every box checked (some = doing, none = todo); also when only `openspec/changes/archive/*-<x>/tasks.md` exists |
| `{"type":"path-exists","path":"<repo-relative path>"}` | the path exists |
| `{"type":"commit","grep":"<pattern>"}` | `git log --grep` on HEAD finds a commit |
| `{"type":"project","project":"<registry name>","evidence":{...}}` | the nested evidence holds in that registered project |

Paths are relative to the repository root — never absolute; another project is named by its
set-core registry name and resolved per machine. A missing path or commit is **not** a verdict:
the status stays as it was (absence cannot tell "not yet" from "not on this machine"). A
project not registered on this machine is reported as `UNRESOLVED` and left alone.

## Creating a board

```bash
set-wave-board init <job> --title "<what the job is>"
set-wave-board add <job> --wave w0 --wave-title "<wave title>" --item <id> --title "<item>" \
    --evidence '{"type":"openspec-tasks","path":"openspec/changes/<x>/tasks.md"}'
# … one add per item; waves appear in the order first used
set-wave-board sync
set-wave-board render <job> --bare -o .set/waveboard/<job>.page.html
```

Then publish the page with the **Artifact** tool:

- `file_path`: the rendered `.set/waveboard/<job>.page.html` (the template with the current
  state as its first frame; `set-wave-board page` prints the bare template's path)
- `capabilities: {"db": {}}`, `icon: "board"`, a one-sentence `description`
- it is **private by default — keep it that way**. Never share it publicly; a job's items name
  the projects and work they cover.

Record the URL, push once, and commit the job file:

```bash
set-wave-board link <job> <artifact-url>
set-wave-board sync            # prints: PUSH <job> <url> <payload-path>
```

Do the push (below), then `git add docs/waveboard/<job>.json` and commit it with an explicit
pathspec. The `.set/waveboard/` files are machine-local and ignored on their own.

## The push procedure

The page reads collection `board`, document `state`. Only you can write it — no script can.

1. `ArtifactData` `action: "set"`, `url: <artifact_url>`, `collection: "board"`,
   `doc_id: "state"`, `file_path: <payload path>`, and `if_version: <last pushed version>` —
   omit `if_version` only when this machine has no push recorded (`set-wave-board pending`
   shows `if_version=N` when it has one). Send the file as it is; never retype the payload.
2. Refused because the document changed or already exists → `ArtifactData action: "get"` on
   the same url / `board` / `state`, then redo step 1 with the version it returned.
3. `set-wave-board pushed <job> --version <the version the set returned>`.

The Stop hook asks for this by itself when a payload differs from the last push: it blocks the
stop once, with the exact call filled in. It stays quiet for 30 minutes per job after that
(`SET_WAVEBOARD_NAG_SECONDS`), on its own continuation, in a linked worktree
(`SET_WAVEBOARD_PUSH=worktree` lifts that), and entirely with `SET_WAVEBOARD_PUSH=off`.

## Cross-machine notes

- The job file travels through git; evidence is re-evaluated on each machine against that
  machine's clone and registry. Pull before trusting a board you did not just sync.
- The **Artifact belongs to whoever published it**. Another person can push only if they were
  given edit access; without it the write fails — say so in one line and carry on. The hook
  backs off; `SET_WAVEBOARD_PUSH=off` silences it on that machine.
- What was pushed is recorded **per machine** (`.set/waveboard/<job>.pushed.json`), so a second
  machine sees the job as pending until it pushes once. With `if_version` pinned, two machines
  cannot silently overwrite each other: a stale write is refused and redone after a `get`.
- `by` on an item is the short hostname of the machine that changed it; set
  `SET_WAVEBOARD_BY` for a different label.

## Commands

```
set-wave-board init <job> --title T [--artifact-url URL]
set-wave-board add <job> --wave <id> [--wave-title T] --item <id> --title T [--evidence JSON]
set-wave-board set <job> <item> <todo|doing|done|blocked|skipped> [--note N]
set-wave-board link <job> <artifact-url>
set-wave-board sync [<job>...]          # PUSH lines on stdout
set-wave-board pushed <job> --version N [--hash H]
set-wave-board pending                  # PENDING lines, if_version=N when known
set-wave-board page                     # path of the page template
set-wave-board render <job> [-o FILE] [--bare]
# common: --repo DIR, --json, --quiet, -v
```
