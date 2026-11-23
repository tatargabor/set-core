## Context

A wave board has two parts:
- a tracked job file per job (`docs/waveboard/<job>.json`);
- a private claude.ai Artifact page, whose database the agent writes with `ArtifactData`.

`bin/set-wave-board` does not import `set_orch`. The fleet reads every known project's job files through
`lib/set_orch/fleet/waveboards.py`, and a test holds the two rule copies together. The owner wants:
- every board to be writable by the whole team;
- the boards to be handled together, with dependencies between them.

## Goals / Non-Goals

**Goals:**
- name the editors and the owner account at the moment a board is published or linked;
- turn a refused push into a request for access;
- let an item wait on another board's item, and show that on both boards and in the fleet.

**Non-Goals:**
- sharing the Artifact automatically. No tool can share one; only a person can, in claude.ai.
- a combined Artifact page across projects. The fleet and `overview` are the combined view for now.
- dependency chains: no transitive resolution and no cycle detection beyond a self-reference.
- a schema bump.

## Decisions

**D1 — The editor list is machine-local, read at run time.** The list holds email addresses, so it never goes into
a repository. That follows the same rule as the leak-scan deny list.
- Path: `SET_WAVEBOARD_EDITORS`, else `~/.config/set-core/waveboard-editors.json`.
- Shape: `owner_account` (string) and `editors` (a list of strings).
- A missing or malformed file is not an error: the share step then says the file is missing and shows its shape.
- The addresses appear in terminal output only. They never go into the job file, the payload or a log line. Logs
  carry counts.

**D2 — The session's account comes from `.claude.json`.** The account is `oauthAccount.emailAddress` in
`$CLAUDE_CONFIG_DIR/.claude.json`, or `~/.claude.json` when that variable is unset. This is what the Artifact tool
publishes as.
- When it cannot be read, the step says "unknown". It never guesses.
- When it differs from `owner_account`, the step says so. Ownership cannot be transferred after publishing, so the
  publish moment is the only cheap point to catch it.

**D3 — A dependency is a field, not an evidence type.** The request suggested carrying it as `project` evidence. The
two mean different things:
- evidence says when an item is **done**;
- a dependency says when it may **start**.

As evidence, a met dependency would mark the dependent item done. What the dependency does reuse is the reference
model of `project` evidence: a project is named by its registry name and resolved per machine. A reference without
`project` points into the same repository.

**D4 — Met means `done`, and only `done`.**
- `skipped` does not release a dependent. A prerequisite that will not happen needs a human to re-plan, so it shows
  as unmet with its status.
- An unresolved reference is unmet, with a reason. Unresolved covers: the project is not registered, the job file is
  missing or unreadable, or the item is missing.

Treating unknown as met would release work in exactly the case nobody can see. This is the opposite of evidence,
where absence leaves the status alone. That asymmetry is deliberate: evidence that cannot be read must not undo a
status, and a dependency that cannot be read must not release one.

**D5 — `waiting_on` and `blocks` are computed into the payload, not stored in the job file.** The job file keeps only
`depends_on`. During sync, each item of the payload gets:
- `waiting_on` when the item is open (not `done`, not `skipped`): its unmet dependencies, each with `status` (null
  when unresolved) and `reason`.
- `blocks`: every item on a registered project's board whose `depends_on` points here, with that item's status.

Both are part of the hashed content. So when the other board's item becomes `done`, this board's payload changes and
the hook asks for a push. That is how "shown on both boards" stays live without either board writing the other.

**D6 — Finding `blocks` scans the registry, within the hook's budget.**
- The scan reads each registered project's `docs/waveboard/*.json`. Reading a few small JSON files per project is
  far inside the 12-second budget.
- This repository is identified by every registry name whose path resolves to its root, plus the implicit "same
  repository".
- A project whose directory is missing contributes nothing.
- The scan never runs git.

**D7 — `set` refuses to start a waiting item.** `set <item> doing|done` on an item with unmet dependencies exits 2
and names them. `--force` overrides, because a person may know that the prerequisite is effectively in place.
- `todo`, `blocked` and `skipped` stay allowed.
- Evidence is not guarded. A sync can still derive `done`, because evidence records what happened, and a board that
  denied a fact would be lying.

**D8 — The page draws a waiting `todo` item as blocked.**
- Waves view: a "waits on" chip listing `project/job/item` and its status.
- Kanban: the item goes to the blocked column.
- Strip and counts: it counts as blocked.
- A `doing` item that waits (it was forced) keeps its status and still gets the chip.
- An item with `blocks` gets a "blocks N" chip, with the references in its tooltip.
- Old payloads without these fields render as before.

**D9 — The fleet computes edges over the boards it already read.** `read_waveboards` resolves each `depends_on` against
the boards in the same read, by project name, job and item. It does no further IO. Each summary gets:
- `deps_out`: `{item, on: {project, job, item}, status, met}`;
- `deps_in`: `{item, by: {project, job, item}, met}`;
- `waiting`: the number of open items with an unmet dependency;
- `deps_unresolved`.

Only ids are returned, never titles. That keeps the fleet's "summaries only" rule. The chip counts the
`deps_unresolved` total in the warning colour, because a dangling reference is a defect that a closed list would
otherwise hide.

**D10 — `overview` is the CLI's combined view.** It runs over the registry and prints one line per board (counts,
waiting, blocks) and then every edge with met or unmet. `--json` gives the same data. It writes nothing.

## Risks / Trade-offs

- **The fleet and the CLI can disagree.** The fleet resolves projects by the names in its own project list, and the
  CLI uses the registry. Since the fleet's list includes the registry, they differ only for names that exist only on
  the messaging bus. Those count as unresolved in the CLI.
- **`blocks` is only as complete as this machine's registry.** A board on a project not cloned here cannot be seen.
  The page cannot tell "nobody waits" from "nobody seen waits", so the chip's tooltip says it was read on this
  machine.
- **A cycle (A waits on B, B on A) blocks both.** That is the correct reading, and both boards show it.
