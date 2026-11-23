> **Superseded 2026-11-23 — closed without implementing the open tasks.** This change extends the
> orchestration engine (E2E gates, decompose/planner, fix-iss, the web project template and the
> run dashboards), which `fleet-era-consolidation` retires (stages 4-5: `retire-orchestration-cli`,
> `retire-orchestration-engine`). Archived with `--skip-specs` semantics: no delta reached
> `openspec/specs/`. Tasks ticked here were shipped; unticked ones were not.

## Why

Auto-escalation creates `fix-iss-NNN-*` change directories AND registers them in `state.changes` via `_register_fix_iss_in_state`. Other paths that produce fix-iss artifacts — operator-driven `/opsx:ff` against an Issues-tab item, investigator outputs that author a proposal directly, manual escalations from forensics work — only write the directory and skip registration. Reconciliation at `reconciliation.py:320-323` then explicitly skips fix-iss directories during sweep (correctly protecting them from deletion) but never adopts them either, so the dispatcher never sees them. Result: the orphan sits on disk with a complete proposal/tasks plan and is never dispatched. Observed live during an active orchestration run where two design-fidelity escalations sat with `0/9` and `0/18` tasks for days while their parent changes burned retry budget on the very issues those fix-iss plans were designed to address. The escalation contract ("we'll create a fix-iss when retry budget exhausts and the fix-iss will run") is broken at the dispatch end.

## What Changes

- A new reconciler `reconcile_fix_iss_orphans(state_file, project_root, *, event_bus=None)` SHALL run on each monitor poll: scan `openspec/changes/` for `fix-iss-*` directories that are NOT present in `state.changes`, and register them with `status=pending` so the existing dispatcher picks them up next cycle. The reconciler SHALL be idempotent and safe under concurrent escalation paths.
- Best-effort parent attribution SHALL derive `parent_name` from `proposal.md` content (HTML comment → Why-line regex → slug-prefix match against existing change names). Confident match yields `depends_on=[parent]`, `phase=parent.phase + 1`. No match yields `depends_on=[]`, `phase=current_phase` (run alongside peers, not stalled).
- Distinct event `FIX_ISS_ORPHAN_REGISTERED` SHALL be emitted per adoption (NOT reuse `FIX_ISS_ESCALATED` which stays reserved for proactive circuit-breaker escalations).
- The existing `escalate_change_to_fix_iss` path SHALL emit an explicit `<!-- parent: <name> -->` comment in its auto-generated proposal.md so the reconciler's attribution becomes deterministic for any future auto-escalations that might still orphan due to other bugs.

## Capabilities

### New Capabilities
- `fix-iss-orphan-registration`: scan-and-adopt logic for `fix-iss-*` directories that exist on disk but are missing from `state.changes` so they get dispatched on the next poll cycle.

### Modified Capabilities
(none)

## Impact

- **Code**: `lib/set_orch/issues/manager.py` (new `reconcile_fix_iss_orphans` function + parent-attribution helper + `<!-- parent: -->` annotation in `escalate_change_to_fix_iss`); `lib/set_orch/engine.py` monitor loop (one call site per poll); no schema changes to `Change` (registration uses existing fields).
- **Behavior**: orphans created mid-run by manual `/opsx:ff` or by future investigator outputs dispatch automatically without operator intervention; orphans accumulated before this change ships are also adopted on first poll after deploy (no migration needed).
- **Observability**: `FIX_ISS_ORPHAN_REGISTERED` event in event stream; INFO log per adoption with derived `parent_name` (or "no-parent" sentinel); WARN log per malformed orphan (missing `proposal.md` skipped, with the directory name).
- **Backwards compat**: `escalate_change_to_fix_iss` path is unchanged in behavior — only the `proposal.md` output gains a `<!-- parent: -->` comment which existing readers ignore. The reconciliation skip-logic at `reconciliation.py:320-323` stays. The reconciler is purely additive.
- **Risk**: parent-attribution heuristics could mis-assign on adversarial proposal.md content. Mitigation: when no confident match, default to the SAFE behavior (run-now via `current_phase`, `depends_on=[]`) rather than guessing.
- **Out of scope**: design-fidelity gate scope-awareness changes (deferred — fix-iss escalations already proposed by operators contain targeted `gate_overrides` waivers, and once they dispatch through this reconciler they'll address gate behavior themselves).
