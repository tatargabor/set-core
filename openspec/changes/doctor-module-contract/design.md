## Context

`set-doctor` (change `set-doctor`, spec `machine-doctor`) checks a developer machine and every
registered project. Today it gets module knowledge by calling two other doctors directly:
- `sac doctor --json`, once, as `sac.doctor/1`, indexed by real path;
- `set-kb doctor --json`, per project.

A family-level doctor in another repository runs `set-doctor` and reads only its exit code. It
then re-implements the agent-bus hook check with its own regex over settings files.

On a real machine the report ended `21 fail, 90 warn`:
- 21 fails were registry entries for deleted run directories;
- 48 warns were "deploy behind";
- 34 warns were bus findings.

One of the bus warns was a project with a live session, no `session-start` hook and no
`watch-guard` hook. That session had built its own `Monitor` watch and was re-reading ~230k
tokens every 30 minutes. `sac doctor --json` already carried everything needed to call this
urgent: `hooks` per kind and `live` seats. `set-doctor` reduced it to `verdict: off` → `warn`.

## Goals / Non-Goals

**Goals:**
- One umbrella. `set-doctor` runs every module doctor that is declared on this machine, and
  attributes each record to a module and a project.
- Adding a module needs a declaration file, not a set-core code change.
- A live session that is burning tokens because of missing bus wiring is a `fail` that names it.
- Real failures stop being outnumbered by stale registry entries.
- A second developer's machine learns which declared modules are missing.

**Non-Goals:**
- Repairs. The doctor stays read-only.
- Token accounting from transcripts. That is a possible later module, not this change.
- Editing the agent-bus or family repositories from here. They adopt the contract on their side.

## Decisions

**D1 — The `doctor/1` record is `set-doctor/1`'s record, plus `path`.** Modules print
`{"schema":"doctor/1","module","checks":[{section,name,status,detail,fix?,path?}]}`. `path`, not
`project`, because a module does not know set-core's registry names. Real-path matching does the
join, the same way the `sac` lookup already works.
*Alternative:* a new richer schema with severities and costs. Rejected: the four statuses already
work, and a second vocabulary would need its own translation layer.

**D2 — Declarations live in `<set-core config dir>/doctors.d/<module>.json`.** The directory is
resolved like the registry (`SET_CONFIG_DIR` → `XDG_CONFIG_HOME/set-core` → `~/.config/set-core`).
B-175 is the cost of a reader that hard-codes the path. The module's own installer writes the
file:
- set-core's `install.sh` writes `set-kb`'s;
- the agent-bus setup command writes `sac`'s;
- the family devkit writes the family doctor's.

Fields: `module`, `command` (argv list), `contract` (`doctor/1`, or a legacy contract id with a
built-in adapter), `install` (one-line hint), optional `timeout_s`.
*Alternative 1:* discovery by scanning `PATH` for `*-doctor`. Rejected: it guesses, and it cannot
report a module that is missing.
*Alternative 2:* a list inside the project registry. Rejected: modules are per machine, not per
project.

**D3 — Legacy adapters, replaced by declaration.** `sac.doctor/1` and `set-kb`'s report keep their
current adapters, so an empty `doctors.d` reproduces today's records exactly. A declaration for
`sac` or `set-kb` takes over that module's invocation: one run, never two. When it names
`doctor/1`, the adapter is bypassed. This lets each module migrate on its own schedule.

**D4 — The bus severity comes from `hooks` and `live`, which `sac` already reports.**
- `fail`: `live` is non-empty AND (`hooks["session-start"]` is empty OR `hooks["watch-guard"]` is
  empty). Without `session-start`, the session never receives the background-watch instruction.
  Without `watch-guard`, nothing declines a `Monitor` watch. Either gap with a live session is
  tokens being spent now.
- `warn`: no hooks and no live seat. Unchanged.
- `warn`: any hook kind with more than one carrier.
- Other `sac` problems pass through as `warn`, as today.

The logic stays in the adapter. When `sac` speaks `doctor/1`, it should emit these records itself.
The rule is written in the spec, so the two cannot drift silently.

**D5 — Stale registry entries become one `stale` warn.** A gone path is a bookkeeping fact, not a
broken system, and 21 of them made every run exit 1. That trained callers to ignore the exit
code, and the family doctor did. The fix is `set-project prune --dry-run`, which already exists.
This does not hide a failure: the count and names stay in the record, and a real `fail` elsewhere
still sets exit 1.

**D6 — Recursion marker `SET_DOCTOR_CHILD=1`.** The family doctor runs `set-doctor`. If it is also
declared as a module, the two would recurse. The marker is set in every module's environment. A
`set-doctor` started under it skips module doctors and says so with one `skip`.

**D7 — Modules run in parallel with the project checks, each once, with a timeout** (default 120 s,
overridable per declaration). Today's cost is ~30 s for 70 projects. Running the `sac` doctor once
was already the pattern, and per-module once keeps the cost additive, not multiplied by projects.

## Risks / Trade-offs

- [A module prints a malformed report] → `fail` for that module with its error tail. The rest of
  the report is still produced, and the module is never shown as clean.
- [A declaration left behind after a module is uninstalled] → it becomes a "declared but not
  installed" warn with the install hint. The reader can reinstall or delete the declaration, and
  the warn says which file.
- [Exit code semantics change for gone paths] → called out as BREAKING in the proposal. The only
  known caller reads the exit code and is being moved to `--json` in the same round.
- [The family doctor keeps its regex until it migrates] → the two may disagree for a while. The
  coordination message names the exact `sac` fields to read instead.

## Migration Plan

1. Ship the adapters and the empty-`doctors.d` path. The report should be identical except for
   the `stale` grouping and the new bus `fail`s.
2. `install.sh` writes the `set-kb` declaration.
3. Agree on the bus with the agent-bus and family-doctor sessions. Each writes its declaration, and
   later moves to `doctor/1`.

Rollback: delete `doctors.d`. The adapters reproduce the current behaviour.

## Open Questions

- Should "deploy behind" (48 warns) also aggregate? It is per project and actionable, so this
  change leaves it alone.
