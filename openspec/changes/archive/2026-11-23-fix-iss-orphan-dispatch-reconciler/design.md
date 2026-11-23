## Context

`escalate_change_to_fix_iss` (lib/set_orch/issues/manager.py) is the auto-escalation entry point: when a parent change hits a circuit breaker (retry budget exhausted, stuck loop, token runaway), it (1) writes `openspec/changes/<fix-iss-name>/proposal.md`, (2) registers the new change in `state.changes` via `_register_fix_iss_in_state`, and (3) emits `FIX_ISS_ESCALATED`. This path works correctly.

There are other paths that produce `fix-iss-*` directories without going through `escalate_change_to_fix_iss`:

- An operator runs `/opsx:ff` against an Issues-tab item to propose a fix-iss.
- The issue investigator writes a `proposal.md` for a discovered defect.
- Forensics work on a completed run produces a fix-iss to track a regression.

These paths only write the directory. Reconciliation (`reconciliation.py:320-323`) explicitly skips `fix-iss-*` entries during the sweep that removes stale change dirs after replan — necessary to avoid wiping legitimate diagnostic artifacts — but the skip is one-way: directories are protected from deletion AND never adopted into state. The dispatcher iterates `state.changes` only, so an unregistered orphan is invisible to dispatch. Operators have no recourse short of manual state edits.

The escalation contract that the framework promises ("when something goes wrong, we'll create a focused diagnostic change that fixes it") is structurally broken at the dispatch end whenever the creation path isn't `escalate_change_to_fix_iss`. This proposal addresses only the registration gap.

## Goals / Non-Goals

**Goals:**
- Orphan `fix-iss-*` directories on disk are adopted into `state.changes` automatically on the next monitor poll, without operator intervention.
- The adoption path is idempotent (safe across concurrent escalations and repeated polls) and forward-only (no migration script needed for orphans accumulated before deploy).
- Operators can audit what was adopted via a structured event distinct from auto-escalation events.
- Authoritative `escalate_change_to_fix_iss` proposals carry a deterministic parent-attribution marker so the reconciler's heuristics never have to guess for them.

**Non-Goals:**
- Modifying any gate logic, gate ordering, or gate retry policy.
- Modifying the design-fidelity gate's behavior or scoping. Fix-iss escalations created by operators against design-fidelity false positives carry their own `gate_overrides` plans; once those orphans dispatch through this reconciler, they self-address the gate behavior.
- Removing orphans (covered by the existing `fix-iss-orphan-cleanup` capability — orthogonal direction).
- Auto-dispatching the fix-iss agent itself; dispatch already works once a change has `status=pending` in state.

## Decisions

### Decision 1: Reconciler runs in the monitor poll loop, not on supervisor start

**Choice:** Add `reconcile_fix_iss_orphans(state_file, project_root, *, event_bus=None)` to `issues/manager.py`. Call it once per monitor poll cycle from the engine's poll entry point, before dispatch evaluation. Wrap the call in try/except so a reconciler failure cannot halt the poll loop.

**Why per-poll, not start-only?** Operators may create orphans MID-RUN via `/opsx:ff` against an Issues-tab item or via forensics work. Supervisor-start-only would force a daemon restart after every manual escalation. Per-poll is the natural cadence and the directory scan is cheap (one `os.scandir` + dict lookup per dir, sub-millisecond for typical project sizes).

**Alternatives considered:**
- *On-demand via API endpoint.* Requires operator action — defeats the goal of zero-intervention.
- *File-watcher (inotify-style).* Heavier, platform-specific, adds dependencies.

### Decision 2: Parent attribution uses three ordered strategies with a SAFE fallback

**Choice:** When registering an orphan, attempt to derive `parent_name` from:

1. An HTML comment of the form `<!-- parent: <name> -->` anywhere in `proposal.md` (preferred — `escalate_change_to_fix_iss` will start emitting this so future auto-escalations are deterministic).
2. A line matching `Parent change \`(.+?)\`` in the Why section (compatible with the current auto-escalation proposal format).
3. Slug-prefix match: the orphan's slug suffix (after `fix-iss-NNN-`) compared against existing change names by prefix; the longest matching change name wins.

If none of the strategies yield a confident match, the orphan SHALL be registered with `depends_on=[]` and `phase=state.current_phase`, NOT with a guessed phase. This is the SAFE choice: the orphan dispatches alongside peers in the active phase rather than being permanently stalled in some far-future phase, and the absence of a depends_on edge means dispatch ordering is decided by phase alone.

**Why ordered strategies with safe fallback?** Heuristic mis-attribution would assign the orphan to the wrong phase. The conservative escape (run now) is far less harmful than the aggressive escape (guess and stall).

### Decision 3: Distinct event type `FIX_ISS_ORPHAN_REGISTERED`

**Choice:** Emit a new event type rather than reusing `FIX_ISS_ESCALATED`.

**Why?** Reusing `FIX_ISS_ESCALATED` would conflate "I just escalated retroactively because I found an orphan" with "I escalated proactively because a circuit breaker tripped". Distinct events let dashboards count orphans-recovered as a separate metric — useful for understanding how often the escalation contract self-heals vs how often the circuit-breaker path produces well-formed escalations end-to-end.

**Alternatives considered:**
- *Reuse `FIX_ISS_ESCALATED` with a `source` field.* Workable but operators reading event-type filters miss the distinction. The cost of a new event type is one constant.

### Decision 4: Idempotency anchored on the existing duplicate-name guard

**Choice:** The reconciler does NOT track its own state. It calls `_register_fix_iss_in_state` (which already short-circuits on `any(c.name == fix_iss_name for c in state.changes)`) under the existing `locked_state` context manager. The duplicate-name guard is the single source of truth for "already registered" — the reconciler asks "do I see this name in state?" outside the lock, and the registration helper enforces it inside the lock.

**Why piggyback on the existing guard?** Splitting the idempotency check between two layers would be brittle — the lock-respecting helper IS the source of truth. Replicating the check in the reconciler buys nothing and risks divergence.

### Decision 5: Adoption tolerates partial artifacts

**Choice:** A directory missing `proposal.md` SHALL be skipped with a WARN log (no registration). A directory missing `tasks.md` or `design.md` SHALL be registered anyway.

**Why?** `proposal.md` is the entry point that supplies parent attribution and scope context — without it, registration cannot proceed safely. `tasks.md` and `design.md` are produced during dispatch by the agent's planning step; the dispatcher already tolerates their absence at registration time.

## Risks / Trade-offs

- **[Risk] Race between `escalate_change_to_fix_iss` and `reconcile_fix_iss_orphans` for the same name.** Both writing to state.changes concurrently. → Mitigation: both go through `locked_state`; the duplicate-name guard inside the lock makes the second write a no-op. Add a unit test that spawns two threads exercising the race.

- **[Risk] Parent-attribution mis-assigns to a wrong phase.** Heuristic could match the wrong slug prefix on an adversarial directory name. → Mitigation: SAFE fallback to `current_phase` when no STRONG match. The slug-prefix strategy requires a meaningful prefix length (configurable; minimum default of 4 characters of slug overlap to avoid one-letter false matches).

- **[Risk] Reconciler runs forever on broken state.** Buggy code in the reconciler could halt the monitor loop. → Mitigation: try/except wrapper with ERROR-level log on exception; the poll loop continues.

- **[Trade-off] Adoption disregards orphans whose parent has been archived.** A `fix-iss-007-foo` whose parent `foo-feature` was archived months ago will be adopted with `depends_on=[]` (since the parent isn't in `state.changes`). → Acceptable: the orphan's findings may still be valid; running it as if its parent disappeared is the right behavior for a stale escalation.

- **[Trade-off] Per-poll scan adds work even when no orphans exist.** The cost is a single `os.scandir` over `openspec/changes/` per poll. → Acceptable: sub-millisecond on typical projects; constant-time relative to the poll period.

## Migration Plan

The reconciler ships unconditionally — there is no failure mode that affects existing behavior (idempotent registration, no destructive operations, no schema changes). After deploy:

1. Existing orphans across all running projects are adopted on the first poll after the orchestrator restart.
2. The `<!-- parent: -->` annotation in `escalate_change_to_fix_iss` is purely additive — existing readers ignore HTML comments. No schema bump needed.
3. Rollback is a single revert. Adoptions made before rollback persist as legitimate state entries — they would have happened anyway when an operator noticed.

## Open Questions

- Should the slug-prefix minimum length be a config knob or a constant? Likely constant (4 characters) — the heuristic is already a fallback and over-configuring it complicates the contract.
- Should `FIX_ISS_ORPHAN_REGISTERED` carry the full proposal.md contents in its `data`? Probably not — events stay slim; the contents are reachable via the registered change's directory. Tasks pin this.
