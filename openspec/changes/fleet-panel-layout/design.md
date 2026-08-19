## Context

The fleet screen has two layout facts today, and one of them is about to stop
being true. The first: the project list is a fixed-width column beside an area
that lays agent tiles out in 1–4 grid columns. The second: **every panel in that
area is an agent terminal**, which is not a rule anybody wrote down — it is what
the code assumes because nothing else has ever been put there.

The user has asked for a view that lists changes and bugs and schedules them in
waves. That view has nowhere to go. Before its content can be designed, the
screen needs to be able to hold a panel that is not an agent, and to give a
docked view space that the grid then works around.

Part of this shipped ahead of the change (`797f7af5`, the draggable divider) and
is documented here retroactively, with its tasks already checked. Doing so is the
repository's stated repair for a contract change that went by direct commit; it
is not a precedent for skipping the artifact.

The constraint that shapes everything below: **the framework layer stays
domain-free.** A panel *type* is a framework word; what a view SHOWS belongs to
the project's side of the abstraction. A design that named "changes" or "bugs"
in the layout layer would put the domain in the framework, which the
architecture rules forbid and the confidentiality boundary would eventually
punish.

## Goals / Non-Goals

**Goals:**
- One divider mechanism, used by every draggable edge on the screen.
- Divider positions stored where the arrangement is, without disturbing it.
- Panels carry a declared type, so the screen can hold more than one kind.
- A docked view takes space out of the grid's area without the grid knowing why.

**Non-Goals:**
- The changes-and-bugs view itself, its selection model, or wave scheduling.
- Worktrees as first-class places in the fleet — that touches discovery.
- Floating, overlapping or free-positioned panels. Docking is to an edge or not
  at all; anything else is a window manager, and a window manager is a project.
- Per-project divider positions. A divider belongs to the screen.

## Decisions

### D1 — Divider positions live in the existing layout document, not a new store

`fleet-layout.json` in the framework's durable per-user root already holds the
hand-made arrangement, and it exists for exactly the reason a divider position
does: work the user does once and relies on, which should not differ between two
browsers on the same machine. A `splits` map keyed by divider goes in beside it.

*Alternative rejected — `localStorage`.* The dashboard uses it for view
preferences, and the module header already argues why the arrangement is not one
of them. A divider position is closer to the arrangement than to a collapse
toggle: a pane can be dragged nearly shut, and finding it that way in a second
browser reads as a broken screen rather than as a lost preference.

*Alternative rejected — a second file.* Two documents describing one screen have
to be kept consistent by whoever writes them, and the failure is silent.

### D2 — Dividers get their own write route, and it does not bump the version

`PUT /api/fleet/layout` is guarded by `base_version`, which is what stops two
open tabs from overwriting a hand-made arrangement. Putting divider writes on
that route forces a choice between two defects:

- **bump the version** → every drag of an edge invalidates the base version the
  open project column is holding, so the user's next group edit 409s against
  their own dragging. A conflict produced entirely by the conflict machinery.
- **skip the guard** → an unguarded write now lives on the route whose whole
  purpose is to guard.

So `PUT /api/fleet/layout/splits` writes positions alone and leaves the version
where it was. **Last-write-wins is deliberate here**: what a race costs is one
number, re-dragged in a second. The same reasoning that makes the arrangement
version-guarded makes the divider not, and that asymmetry is the point of
separating them.

### D3 — Omission preserves; an explicit empty map clears

`normalise` returns `{}` for both "no dividers" and "not mentioned", so the
project column — which posts groups and says nothing about dividers — would wipe
every dragged edge on each drag of a project. The whole-document body therefore
carries dividers as an omissible field: absent means leave alone, present means
replace. Without the second half there would be no way to reset.

### D4 — An absent position is the caller's default, never a zero

The false-absence class, in the direction that costs most: a pane stored at zero
renders as no pane, and the edge needed to drag it back is exactly what is no
longer on screen. So an unusable value is **dropped** rather than coerced —
dropping restores the default, coercing invents a position the user never chose.

### D5 — Two clamps, because they answer different questions

The server clamps to what is **recoverable** (an edge that can be grabbed again);
the client clamps to what **fits** (the shell's real width, minus the room the
agent panel needs to stay useful). Neither is sufficient alone: the server cannot
see the viewport, and the client cannot stop a hand-edited file from arriving.
Collapsing them into one number would have to pick a wrong side.

### D6 — The divider component knows both axes and both sides from the start

`axis: 'x' | 'y'` and `grows: 'before' | 'after'`, even though only one
combination is used today. Not speculative generality: the docking requirement
in this same change needs the other three, and the alternative is a copy. A copy
is where the keyboard support, the pointer capture and the bounds get left out —
they are the parts nobody notices missing until somebody cannot use the screen.

### D7 — Panel type is declared by the opener, never inferred

The same shape `agent-goal-and-lifecycle` reached for goals and `fleet-view`
reached for lineage: a fact that exists at the moment of the act cannot be
recovered later by inspecting the result. A screen that guessed a panel's type
from its contents would be wrong exactly when the contents are unusual, which is
when it matters. An unknown type is reported as unknown — not rendered as the
type it resembles.

### D8 — The grid is handed a smaller box; it learns nothing about docking

Docking removes space; the grid lays out in what is left. If the grid knew about
docked views it would need a rule per edge, and every new view type would have to
be taught to it. The column count therefore keeps meaning what the user chose —
three columns stays three columns, in a narrower area.

### D9 — Docking is to an edge or not at all

Floating panels imply z-order, focus, collision and restore-position, and each of
those is a system. An edge dock has one degree of freedom — its size — which is
the divider that already exists.

## Risks / Trade-offs

- **A divider dragged nearly shut looks like a missing feature.** → Both clamps
  keep the pane grabbable, and the client's maximum is measured against the shell
  rather than assumed, so the agent panel keeps a usable minimum.
- **Last-write-wins on positions between two tabs.** → Accepted, and stated in
  D2: the loss is one number. The arrangement, which is real work, keeps its
  guard.
- **Docking creates a new place a failure can hide.** → `ui-quality.md`'s rule is
  lifted into a requirement rather than left as a convention: a collapsed docked
  view must mark a failed item on the edge where the reader stands. This is the
  requirement most likely to be quietly skipped, because a screen without it
  looks finished.
- **The panel-type registry could become a place domain leaks into.** → A type is
  an identifier plus a renderer; nothing about what the view fetches belongs to
  it. A review of this change should check that no type name in the layout layer
  names a domain concept.
- **A stored layout can reference a view type a later build removed.** → Same
  rule as a project named in an arrangement that no longer exists: report it,
  do not silently drop it.

## Migration Plan

No migration. `splits` is additive and absent in every existing stored document,
which the reader already treats as "no dividers" and renders at defaults. Rolling
back the server leaves the field in the file, where the older `normalise` drops
it on the next arrangement save — a lost preference, not a broken screen.

## Open Questions

- **Does a docked view instance belong to a project, or to the screen?** The
  divider is the screen's; a view listing one project's changes may not be. This
  decides whether docking state is stored once or per project, and it is
  deliberately left to the change that builds the first real view — answering it
  from an empty layout layer would be inventing a requirement.
- **What happens to a docked view when its project disappears?** Follows from the
  above, and the arrangement's existing answer (report, do not drop) is the
  candidate.
