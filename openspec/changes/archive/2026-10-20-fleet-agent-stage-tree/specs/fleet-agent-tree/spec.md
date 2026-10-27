## IN SCOPE

- Indented agent sub-rows under each project row in the fleet project column
- Selecting an agent by clicking its sub-row
- A compact per-agent stage strip on the sub-row (done / current / pending / empty / outside the flow)
- Visible marking of stage gaps on the sub-row

## OUT OF SCOPE

- Deriving or overriding the stage values themselves (covered by `agent-stage-derivation`)
- The project-status table's stage strip and its semantics (already specified; unchanged)
- Docking, tabs, terminal panels, and the content-area agent grid (existing behaviour, unchanged)
- Recorded (not-live) sessions as sub-rows

## ADDED Requirements

### Requirement: Each project row renders its live agents as always-visible indented sub-rows

The fleet project column SHALL render, beneath each project row, one indented sub-row per live
agent of that project, for EVERY project row that holds live agents — not only the selected one
(amended 2026-08-30 at the user's request: *"subprojects tree must be shown all the time — don't
hide not-selected subprojects"*). Sub-rows SHALL be visually subordinate to the project row
(indentation, reduced weight), so the tree reads as agents belonging to the project without a
second screen. Project-level behaviour — filtering, sorting, the live/arrangement mode, the
row's own counts — SHALL continue to operate on project rows exactly as before.

#### Scenario: A project with live agents shows them as sub-rows

- **WHEN** a project row is rendered for a project whose fleet payload carries live agents
- **THEN** one indented sub-row appears beneath it per agent — whether or not the project is
  selected — and no agent appears under a project it does not belong to

#### Scenario: Project-level filtering still applies to the tree

- **WHEN** the column is filtered (query or live mode) so a project row is hidden
- **THEN** that project's agent sub-rows are hidden with it, and no orphaned sub-row remains

### Requirement: Clicking an agent sub-row selects that agent

Clicking an agent sub-row SHALL select the project and focus that agent, with the same effect as
selecting the agent's tile in the content area today. The selection SHALL be remembered per
project by the same mechanism the content area uses, so returning to the project restores the
same focused agent.

#### Scenario: A sub-row click focuses the agent

- **WHEN** the user clicks the sub-row of an agent of the selected project
- **THEN** that agent becomes the focused agent of that project, exactly as if its tile had been
  clicked in the content area

#### Scenario: The selection survives leaving and returning

- **WHEN** the user focuses agent A of project P via its sub-row, selects another project, then
  returns to P
- **THEN** agent A is focused again

### Requirement: Each agent sub-row renders its stage as a numbered-circle pipeline

Each agent sub-row SHALL render the agent's resolved flow on its own line beneath the agent's
name, as NUMBERED CIRCLES connected in declared order — circle 1 is the flow's first stage,
the highest number its last (amended 2026-08-30 at the user's request: *"little circles like
1-2-3-4-5-6-7 where 1 is the start and the last is the final — more representative than just
the name"*). Completed circles, the current circle, and pending circles SHALL be visually
distinct at a glance (one visual weight per meaning — one style means done, one means running,
one means pending, consistently across every sub-row). The current stage's NAME SHALL be
rendered beside the circles, so nothing load-bearing depends on hover; every circle SHALL carry
its stage name as hover text. A value outside the flow SHALL be marked, never dropped. The
pipeline SHALL stay legible at sub-row height and SHALL NOT depend on hover or expansion to
show the current stage.

#### Scenario: Mid-flow agent reads at a glance

- **WHEN** an agent is resolved at position `apply` of the flow `[proposal, design, apply, verify, archive]`
- **THEN** the pipeline renders five circles numbered 1–5 with connectors, circles 1 and 2 in
  the completed style, circle 3 (apply) in the running style, circles 4 and 5 in the pending
  style, and the name `apply` rendered beside the circles

#### Scenario: Nothing started renders the empty state

- **WHEN** an agent carries a gap because nothing was ever started for it
- **THEN** the strip renders the empty state — visibly different from any resolved position, and
  different again from a gap caused by a resolution failure

#### Scenario: An outside-the-flow value is marked on the strip

- **WHEN** an agent's stage value does not appear in its flow
- **THEN** the strip shows the value distinctly marked as outside the flow, alongside the full
  declared flow, and never drops either the value or the flow

#### Scenario: A declared flow renders in the producer's own stages

- **WHEN** a project declares a flow whose stage names are not OpenSpec stages
- **THEN** the sub-row pipeline renders one circle per producer stage in the declared order,
  each carrying its producer stage name, with the same done/running/pending mechanics as the
  derived flow, and the current stage's producer name rendered beside the circles
