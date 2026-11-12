---
name: set:wave-board
description: Live execution status of a multi-step job that runs in waves — a cleanup across ten projects, a migration done one group at a time, any job with more steps than one session holds. Use it to create the job's board (a tracked job file plus a private claude.ai Artifact page), to report a finished step, and to push the board to its Artifact when the user asks for it (the Stop hook is off by default). Trigger words - wave board, hullámtábla, waves, process roadmap, "where is the job", multi-project cleanup, rollout status, `set-wave-board`, a Stop-hook reminder that names a wave board.
---

# Wave board — `set-wave-board`

A **process roadmap**, not a product roadmap: which wave a job is in, which item is done, in
progress or blocked, and what is left. One job is one tracked file,
`docs/waveboard/<job>.json`, in the repository that runs the job. That file is the board's
default target: a team portal can build its pages from it. An optional private Artifact page shows
it live, but it is pushed **on request only** (see below).

> **Pushes go on request (owner, 2026-11-12).** `set-hook-waveboard` is OFF unless a machine sets
> `SET_WAVEBOARD_PUSH=on`. Without it, no sync runs on Stop and no push or review is asked for,
> because each one costs a whole continuation. Keep the job file current with `set`, commit it,
> and push to the Artifact only when the user asks.

## When to use it

Use a board when a job has **several steps that outlive one session** or run across several
projects: the status must survive a compact, a `/clear`, a second machine and a second person.
A three-step task done in one sitting does not need one; a todo list is enough there.

## How the status stays true — three layers

1. **The job file** — waves, items, and for each item the **evidence** that proves it.
2. **`sync`**: it derives status from evidence. Run it by hand (`set-wave-board sync`) when
   you want the derived status. On a machine that opted in (`SET_WAVEBOARD_PUSH=on`), the
   `set-hook-waveboard` Stop hook also runs it on every stop.
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
  the projects and work they cover. Share it only with the team's editors (below).
- **publish it from the owner account.** `init --artifact-url`, `link` and `share` say which
  account that is and whether this session is signed in as it. An artifact cannot change owner
  later, so a board published from the wrong account is the one thing worth stopping for.

Record the URL, push once, and commit the job file:

```bash
set-wave-board link <job> <artifact-url>
set-wave-board sync            # prints: PUSH <job> <url> <payload-path>
```

`link` also prints a `SHARE` line: the board URL and every editor who must get **edit access**.
Sharing is a person's act on claude.ai (open the board → Share → invite with edit access) — no
tool can do it — so pass the line on to the user. `set-wave-board share` prints it again for
every board in the repository, published or not.

Do the push (below), then `git add docs/waveboard/<job>.json` and commit it with an explicit
pathspec. The `.set/waveboard/` files are machine-local and ignored on their own.

## Who can write a board — the editor list

Every editor on the team must be able to push every board. The list of who that is lives on
each machine, never in a repository, because it holds addresses:

```json
// ~/.config/set-core/waveboard-editors.json   (or the path in SET_WAVEBOARD_EDITORS)
{"owner_account": "<the account that publishes boards>", "editors": ["<email>", "..."]}
```

Never copy an address from it into a job file, a note, a commit or a log.

## The combined board — the team's boards on one shared page

The team reads Artifacts, not the fleet or the CLI, so every board in the team's scope also
lands on ONE shared page: a second Artifact whose database holds collection `boards`, one
document per board (`<project>--<job>`). The editor list on each machine carries it:

```
"combined_url": "<the combined board's URL>",
"projects": ["<registry name or fnmatch pattern>", "..."]
```

- **Scope is mandatory.** Only repositories whose registry name matches `projects` go there —
  the page is shared, and a machine holds more projects than the team's. Without `projects`
  nothing is pushed to it.
- With both set, `sync` also prints `PUSH-COMBINED <job> <url> boards/<doc> <payload>`, and the
  Stop hook's block carries that push next to the board's own. Same procedure, with
  `collection=boards`, `doc_id=<doc>`, and `set-wave-board pushed <job> --combined --version N`.
- Publishing it once: `set-wave-board combined-page --bare -o <file>`, publish the file with the
  Artifact tool (`capabilities: {"db": {}}`) from the owner account, then
  `set-wave-board combined-link <url>` on **every** machine of the team, and share the page with
  the editors (the printed SHARE line).
- `set-wave-board overview` follows the same scope; `--all` lists every registered project.

## Dependencies between boards

Boards stay one file per job, but an item may wait on another board's item — in this
repository or in another registered project:

```bash
set-wave-board add <job> --wave w1 --item migrate --title "…" --depends-on tooling:build/cli
set-wave-board depend <job> <item> [project:]job/item ...
set-wave-board undepend <job> <item> [project:]job/item ...
```

- A dependency says when an item may **start**; evidence says when it is **done**. They are
  different fields — do not express a prerequisite as evidence.
- It is met only when the other item is `done`. `skipped`, a project not registered here, a
  missing board or item: all unmet, with the reason shown.
- While it is unmet, `set <job> <item> doing|done` is refused and names what it waits on.
  `--force` exists for when the prerequisite is in place in fact; say why in `--note`.
- `sync` puts `waiting_on` and `blocks` into the pushed payload, so **both** boards show the
  link, and the waiting board is pushed again when the other item finishes.
- `set-wave-board overview` lists every registered project's boards and every edge, met or not.
  The fleet's wave list shows the same as "waits on N" / "blocks N".

## The push procedure

The page reads collection `board`, document `state`. Only you can write it — no script can.

1. `ArtifactData` `action: "set"`, `url: <artifact_url>`, `collection: "board"`,
   `doc_id: "state"`, `file_path: <payload path>`, and `if_version: <last pushed version>` —
   omit `if_version` only when this machine has no push recorded (`set-wave-board pending`
   shows `if_version=N` when it has one). Send the file as it is; never retype the payload.
2. Refused because the document changed or already exists → `ArtifactData action: "get"` on
   the same url / `board` / `state`, then redo step 1 with the version it returned.
3. `set-wave-board pushed <job> --version <the version the set returned>`.

**Do it when the user asks.** On a machine that opted in (`SET_WAVEBOARD_PUSH=on`) the Stop hook
asks for it too, but **in batches, not after every `set`** — every push
costs a continuation, and a push per step burned the team's token budget (owner, 2026-11-08).
`sync` classes each pending push, and the hook decides per job:

| class | what changed since the last push | the hook |
|---|---|---|
| `first` | nothing recorded on this machine yet | asks at once |
| `milestone` | a wave finished, or an item turned `blocked` | asks at once |
| `progress` | statuses, titles or dependencies, no milestone | asks only when the last push is ≥ 1 hour old (`SET_WAVEBOARD_DEBOUNCE_SECONDS`) |
| `notes` | only notes, `updated`/`by` stamps, evidence definitions | never asks; rides with the next push |

A board and its combined-board document are asked for in **one** block — push both in that one
go. After a block it stays quiet for 30 minutes per job (`SET_WAVEBOARD_NAG_SECONDS`), on its
own continuation, in a linked worktree (`SET_WAVEBOARD_PUSH=worktree` lifts that), and entirely
unless `SET_WAVEBOARD_PUSH` is `on` (the default is off).

**On an opted-in machine only:** before a handoff and at the end of a session, run
`set-wave-board pending` and push what it lists. The hook cannot tell the last Stop of a session
from any other, so batched progress and notes would otherwise wait for the next session. On any
other machine, commit the job file and stop there.

## Cross-machine notes

- The job file travels through git; evidence is re-evaluated on each machine against that
  machine's clone and registry. Pull before trusting a board you did not just sync.
- The **Artifact belongs to whoever published it**. Another person can push only if they were
  given edit access. If the write is refused for lack of access, **ask the owner account for
  edit access** (claude.ai → Share), say so in one line and carry on. If the artifact belongs to
  an account this machine cannot get access to, the machine should not opt in at all.
- What was pushed is recorded **per machine** (`.set/waveboard/<job>.pushed.json`), so a second
  machine sees the job as pending until it pushes once. With `if_version` pinned, two machines
  cannot silently overwrite each other: a stale write is refused and redone after a `get`.
- `by` on an item is the short hostname of the machine that changed it; set
  `SET_WAVEBOARD_BY` for a different label.

## Commands

```
set-wave-board init <job> --title T [--artifact-url URL]
set-wave-board add <job> --wave <id> [--wave-title T] --item <id> --title T [--evidence JSON]
set-wave-board set <job> <item> <todo|doing|done|blocked|skipped> [--note N] [--force]
set-wave-board link <job> <artifact-url>   # prints the SHARE line
set-wave-board share [<job>...]            # the SHARE line again, per board
set-wave-board depend|undepend <job> <item> [project:]job/item ...
set-wave-board overview [--all]            # the team's boards and edges (--all: every project)
set-wave-board combined-page [-o FILE] [--bare]
set-wave-board combined-link <url>
set-wave-board pushed <job> --combined --version N
set-wave-board sync [<job>...]          # PUSH lines on stdout
set-wave-board pushed <job> --version N [--hash H]
set-wave-board pending                  # PENDING lines, if_version=N when known
set-wave-board page                     # path of the page template
set-wave-board render <job> [-o FILE] [--bare]
# common: --repo DIR, --json, --quiet, -v
```
