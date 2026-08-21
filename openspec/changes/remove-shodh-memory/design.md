## Context

The memory subsystem is not a leaf. It reaches 63 live files across `lib/`, `bin/`, `tests/`,
`mcp-server/` and `templates/`, 70 documentation files, 45 capability specs, 27 of the MCP
server's 35 tools, and — until today — nine hooks in 36 projects on this machine. Removing it
is a sweep, and a sweep is where a removal quietly takes something else with it.

The operationally urgent half is already done and is *not* re-planned here: the hooks are
unbound everywhere (verified: zero `set-hook-memory` in any `settings.json` under `~/code2`
and `~/code`), both daemons are stopped, and the store is archived and verified
(3.3 GB → 345 MB zstd, 81 346 entries, plus a 7885-record JSON export and the one open todo).
So nothing is bleeding while this change is implemented, which is why it can be done properly
rather than fast.

What remains is the code, the contracts and the rule book — and the rule book is the part
that matters most, because CLAUDE.md currently instructs **every session, on every prompt**,
to scan for an injected block that no component emits. A wrong instruction outlives wrong
code: the code stops running, the instruction keeps being followed.

## Goals / Non-Goals

**Goals:**

- The framework installs, ships and depends on no memory subsystem.
- No path can reinstall it. `set-deploy-hooks` is the root cause and is fixed first.
- `set-audit` stops telling projects to reinstall what was removed — its polarity inverts.
- What is lost is written down, so the next session meets a documented absence rather than a
  missing feature.
- The two entangled capabilities are dropped **out loud**, not silently.

**Non-Goals:**

- Adopting a replacement memory system. Nothing is chosen until the native layer is
  *measured* insufficient.
- Deleting the archive. Separate, explicitly approved step.
- Porting the GTD todo system to another substrate.
- Re-litigating the hook removal already shipped in 35 other projects.

## Decisions

### D1 — Fix the deployer before deleting anything

`bin/set-deploy-hooks` both emits the nine hooks and carries a `--no-memory` strip. The strip
becomes unconditional and the emission is deleted, **in the first task**, before any file is
removed.

*Why this order:* every one of the 36 projects is cleaned by its next `set-project init`
without anybody visiting it. If the deletion happened first, the window between "the scripts
are gone" and "the deployer stopped naming them" is a window where an init writes hooks
pointing at executables that no longer exist — nine broken hooks in a consumer tree, failing
on every prompt.

*Alternative considered:* delete `bin/set-hook-memory` first and let the hooks fail harmlessly.
Rejected — a hook that cannot run does not error visibly, it just stops enforcing, and this
repo has already paid for that lesson once.

### D2 — Remove 45 capability specs wholesale, not as 45 delta files

Forty-five specs exist *because* the subsystem existed. A `## REMOVED Requirements` delta for
each would restate roughly 250 requirements, every one with the same `Reason` and the same
`Migration: none`.

The five specs that get real deltas are the ones describing behaviour that **survives and
changes**: `hook-auto-install`, `hook-config-downgrade`, `mcp-consolidation`, `help-command`,
`project-health-scan`. The 45 are listed by name in the proposal and deleted by a task.

*Why this is stated rather than done quietly:* it is a deviation from the per-spec delta
convention, and a deviation nobody wrote down is indistinguishable from an oversight at
review time.

*Alternative considered:* generate the 45 deltas mechanically. Rejected — 250 auto-written
requirement restatements is 250 things a reviewer must skim to find the five that matter.

### D3 — `project-health-scan` inverts rather than drops its check

The obvious move is to delete the memory-hook check from `set-audit`. Keeping it, inverted,
is better: the 36 projects were cleaned today, but a project restored from a backup, a
worktree created from an old branch, or a machine that missed the sweep will still carry the
nine. Inverted, the audit *finds* them. Deleted, it is silent about exactly the case that
motivated the change.

### D4 — The two entangled capabilities are dropped, and named

- `load_matching_rules()` (`lib/set_hooks/memory_ops.py:129`) reads `.claude/rules.yaml` and
  is entirely shodh-independent — a YAML matcher that happens to live in the memory hook.
  **Zero projects on this machine have a `rules.yaml`** (measured). It goes with the hook.
- The GTD todo system **is** shodh-backed. One open todo (2026-04-20) is already in the
  archive. Todos are dropped, not ported.

Both are recorded in the proposal's Impact rather than discovered by whoever next types
`/set:todo`.

### D5 — `--no-memory` is accepted and becomes a no-op, not an error

Callers exist — the benchmark baseline path, and any script or muscle memory. Rejecting the
flag turns a removal into a breakage in unrelated tooling. It is accepted and does nothing,
because the behaviour it selected is now the only behaviour.

### D6 — Documentation is retargeted, and one document is kept as evidence

`docs/research/shodh-memory-audit.md` stays. It is the February measurement that found the
empty knowledge graph six months before anyone acted on it, and deleting it would remove the
record of how long the finding sat unactioned. The other 69 files are retargeted or removed.

### D7 — The removal is proven, not asserted

A removal is the easiest kind of change to believe without checking, because everything it
touches disappears. The verification tasks therefore assert **the thing**, not a proxy:

- no `set-hook-memory` in any `settings.json` on the machine — the same sweep that measured
  the 36, re-run;
- no module under `lib/` or script under `bin/` imports `shodh_memory`, `set_memoryd` or
  `set_hooks`;
- the unit suite compared against a baseline worktree by **set diff**, with the `PYTHONPATH`
  isolation and the session-end leak assertion CLAUDE.md prescribes — because this repo is
  installed editable and a `cd` into a worktree is a proxy for running its code;
- the two safety hooks still fire, asserted by invoking them, not by grepping the config.

## Risks / Trade-offs

**[A stale `set-memory` call survives somewhere and fails at runtime]** → The grep is over
`lib/`, `bin/`, `mcp-server/`, `templates/`, `.claude/` and `modules/`, not over the files the
change happens to touch. A surviving call is a missing removal, and the check must be able to
find one it did not expect.

**[`set-audit` reports ❌ on 36 projects at once]** → Correct and intended. They were cleaned
today, so the finding should be empty; if it is not, the sweep missed something and the audit
is the thing that says so.

**[The framework loses semantic recall over thousands of records]** → Accepted, and this is
the trade the measurement argues for: the subsystem had semantic search, tags, temporal
queries, full-text search, cross-device sync, version history and automatic extraction, and
it produced **one reusable line in 187 injections over 21 days**. Losing seven capabilities
that jointly delivered that is not a cost worth mitigating.

**[The native index silently truncates at 200 lines / 25 KB]** → Real and near-term: one
project's `MEMORY.md` is already 123 lines / 20 550 bytes. Content past the cut loads for
nobody and nothing warns. The `native-memory-layer` spec makes the limit a stated requirement
and an index over 150 lines / 20 KB a reportable condition.

**[Someone reinstalls a memory system to fill the gap]** → The gap is documented as
deliberate, with the number attached. A replacement is a change of its own, and it has to be
measured against the native layer rather than against the vacuum.

## Migration Plan

1. Fix `set-deploy-hooks` (D1). Projects self-clean from here.
2. Invert `set-audit` (D3), so the fleet can be checked.
3. Remove the MCP tools, then the CLI and daemon, then the libraries — outermost surface
   first, so a missed caller fails loudly at the boundary rather than deep inside.
4. Rewrite CLAUDE.md's Persistent Memory section and the `.claude/` commands and rules.
5. Delete the 45 specs; retarget the docs; keep the audit document.
6. Remove the tests that test the removed code; keep any that assert its **absence**.
7. `pip uninstall shodh-memory` from both interpreters — miniconda 0.1.81 and linuxbrew
   0.1.90.
8. Run the verification set (D7).

**Rollback:** every step is a commit, and the store is archived and verified. Restoring is
`git revert` plus `tar -I zstd -xf shodh-store.tar.zst`. Nothing in this change destroys data;
the one destructive act — deleting the archive — is explicitly out of scope.

## Open Questions

- **Does anything outside this repository call `set-memory`?** The 36 projects' `.claude/`
  configs are clean, but a project's own script could shell out to it. Worth a sweep over
  `~/code2` and `~/code` for `set-memory` outside `.claude/settings.json` before step 7, and
  the answer belongs in the tasks rather than in someone's head.
- **Do the framework's own skills degrade gracefully?** `/opsx:explore` and `/opsx:apply`
  pass `--mode causal` / `--mode associative`. Those modes were measured to be aliases of
  semantic, so nothing is lost — but the call sites still have to go, and it is worth
  confirming no skill *branches* on a recall result rather than merely quoting it.
