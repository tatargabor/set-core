## Context

`registry-prune` shipped with one archiving path: a threshold plus the E2E-run location, and a
refusal for anything with open issues or a live process. On the live registry that refusal
correctly held back four E2E runs. The operator has now looked at those four and wants them
archived, which the current surface cannot express.

The temptation is a `--force` on the bulk path. That would be the wrong repair: it puts the
override on the *selection* mechanism, so a single flag would silently widen every future bulk
run. The distinction worth encoding is not force-vs-not, it is **selected-by-rule vs
named-by-a-human**.

## Goals / Non-Goals

**Goals:**
- Let an operator archive and unarchive specific entries by name.
- Keep the bulk path's refusals exactly as they are.
- Make the reverse trip real, not just theoretically available in a function.

**Non-Goals:**
- Any `--force` on `--archive-e2e-older-than`.
- Deleting anything. Archiving remains a flag on a kept entry (`registry-prune` D3).
- Age or location filtering on the named path — there is no selection to constrain.

## Decisions

### D1 — Open issues warn; a live process refuses

The two refusals in the bulk path exist for one reason (don't hide a failure) but they are not
the same kind of fact.

An **open issue** is *information about the past* — it stays visible either way, because the
sidebar's issue total reads a separate endpoint. Measured after the previous archiving run:
the total stayed at 14 across 15 archived entries, unchanged. So an operator naming the
project can reasonably decide it no longer needs a row on the overview.

A **live sentinel or orchestrator PID** is *present state*. Hiding a project that is doing
something right now makes the dashboard lie about what the machine is doing, and no amount of
operator intent makes that useful. It refuses, with no override — stop the process first.

A test that refused both would kill the requested feature; a test that allowed both would make
the dashboard wrong. The split is the design, so both halves are asserted separately.

### D2 — A missing directory refuses, pointing at the other command

Archiving means "keep this entry, stop showing it". An entry whose directory is gone should be
*deregistered*, and `set-project prune` does that. Archiving it instead would leave a dead
entry hidden behind a flag — the worst of both, and invisible.

### D3 — An unknown name aborts everything, before any write

`set-project archive a b c` with `b` misspelled must not archive `a` and `c`. Partial
application of a multi-argument command is the shape where an operator believes the whole
command succeeded — the failure is one line of output up the scrollback, and the state is
half-changed. Validate every name first, write nothing if any fails.

### D4 — Archiving the default clears the default, loudly

Measured on the live registry: `default` names one of the entries to be archived. An archived
default is absent from the overview yet still the default for every command that resolves one
— a pointer that looks configured and behaves as if nothing is set.

`registry-prune` already clears a *deregistered* default (`_clear_dangling_default`). The same
applies here, with one addition: it must be **reported**, not just done. A default that
vanishes silently is a configuration change nobody can later trace.

### D5 — One implementation, one write path

`archive_by_name()` lives beside the bulk path in `registry_prune.py` and reuses the same
helpers, including `backup_registry()` before the first mutation. A second archiving
implementation would be a second definition of what "archived" means, and the two would drift
— the same reason `registry-prune` D3 rejected a separate `archived.json`.

## Risks / Trade-offs

- **Operator archives something that mattered** → `unarchive` restores it exactly, and the
  timestamped backup holds the prior registry.
- **The named path becomes the habitual way to skip the bulk refusals** → it cannot be: it
  takes explicit names, never a pattern or a threshold, so skipping the refusal for N projects
  costs N deliberate names.
- **`archived` and a live process race** (process starts between the check and the write) →
  the window is milliseconds and the outcome is a hidden row, not lost data; `unarchive` fixes
  it. Not worth a lock.

## Migration Plan

No migration: entries without `archived` behave as today, and the bulk path is untouched.
Rollback for any single run is `unarchive`, or restoring the timestamped backup.

## Open Questions

None.
