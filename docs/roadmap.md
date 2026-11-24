# Roadmap

Updated for v2.0.0 (2026-11). The April 2026 roadmap — OpenSpec 1.2 migration, an NIS2 layer, a
shadcn/ui design connector, the core/web layer cleanup — was written for the orchestration engine
and is kept in [archive/roadmap-2026-04.md](archive/roadmap-2026-04.md).

Each item below is an OpenSpec change in `openspec/changes/`; the change is the source of truth,
this page is the map. Status figures are tasks done / total, measured 2026-11-24.

## 1. Retiring the orchestration engine, in stages

The engine is dormant in v2.0.0. It leaves in stages, each its own change with a precondition that
is measured, not assumed ([why](learn/from-orchestration-to-harness.md)).

| stage | change | status | precondition |
|---|---|---|---|
| 1–2 | `fleet-era-consolidation` — dead code out, unused consumer artifacts no longer deployed, role rules, log hygiene | 46/55, shipped in v2.0.0 | — |
| 3 | `hook-diet` — unwire the skill-tracking hooks, remove the git-bus MCP tools and `set-control*` bins | 5/7 | a reader check for the hooks' output |
| 4 | `retire-orchestration-cli` — the orchestration bins and their commands' specs | proposed | `set-project init` calls none of them |
| 5 | `retire-orchestration-engine` — engine, planner, dispatcher, verifier, merger, sentinel, their API routes and web pages | proposed | a week of route-hit counts; a regression-baseline set diff |
| 6 | `profile-layer-decision` — what of the modules and profile deploy `init` still needs | proposed | stage 5 done |
| — | `operator-plugin-split` — operator-specific integrations move behind plugin seams into a private package | not started | the public core runs without the package |

## 2. The fleet knows why an agent exists

The fleet can say an agent is alive and what it is doing; it cannot yet say what it was started
for, who it works for, or which session answers for a project.

- `agent-goal-and-lifecycle` (4/78) — record an agent's goal at start and carry it through its life.
- `fleet-mandate-and-desk` (58/125) — mandates, and the desk that answers for a project.
- `fleet-waiting-on-you` (17/33), `relay-answerable-blocking-points` (39/46), `fleet-relay-teach`
  (0/26) — what waits on the human, and teaching the relay to answer more of it.

## 3. The work cycle

Sectioned apply runs as a framework mechanism, with a person in the loop only where one is needed.

- `work-cycle-engine-apply-first` (175/177), `work-cycle-run-visibility` (81/91).
- `work-cycle-question-outbound` (0/47) — a question a cycle raises reaches the person off the machine.
- `work-cycle-answer-is-data` (0/21) — the answer is carried as data, never interpolated as instructions.

## 4. Enforcing the rules, not only writing them

- `adversarial-review-and-gate-layer` (0/81) — a gate layer that enforces the development rules
  this repository already states.
- `session-distillation` (0/52) — the one capability of the removed memory subsystem that was
  asked back, designed against every way the old one failed.
- `tui-design-system-foundation` (35/75) — the dashboard's design system, enforced.

## 5. Open-source hygiene

- **Archive what shipped.** About fifteen changes are shipped and not archived (see the
  [v2.0.0 notes](release/v2.0.0.md)). Adding changes without archiving them is this repository's
  known failure mode.
- **The leak scan's own-repository line.** A reference to one of the owner's own private
  repositories may appear in a public file (a relation, no content); a client's name may not. The
  scanner does not draw that line yet (B-225 in `openspec/bugs/README.md`).
