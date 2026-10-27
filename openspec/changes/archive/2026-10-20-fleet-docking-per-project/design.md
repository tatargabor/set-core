# Design

## The decision: project is part of the key, not a scope preference

A dock entry is `{kind, id, edge}`. For `kind: "agent"` the `id` is a terminal
label, which the framework issues per agent, and an agent belongs to a project.
So the stored entry was always half an identity: it named *what* was docked
without naming *where that thing exists*. Keying by project completes it.

That is why the fix is not a filter on the render path. A filter would leave the
document able to express a state the screen cannot render — the same defect one
layer down, waiting for the next reader of the file.

## Why a write without a project is refused instead of defaulted

A default (the selected project, the first key, an empty string) restores the
old behaviour for any caller that forgets the argument, silently, and only for
someone who had docked something. The missing project is the defect; a signature
that cannot express it is the guard.

## Why the legacy list is preserved and not adopted

A deleted entry and one that was never written are indistinguishable. So the old
flat list survives under `docks_legacy`, stated in the API answer.

It is not adopted into a project, because the document cannot say which project
an entry belonged to. Only the live agent inventory could answer that, by joining
the label against each project's agents — and that join is exactly the guess that
produced the original defect when it went the other way. The cost of not
adopting is one click per band; the cost of guessing wrong is a band appearing
in a project nobody put it in, which is the thing being fixed.

## What deliberately stays screen-wide

Divider positions. The project column's width is a property of the window, not
of a project, and a docked band's size is keyed by the band's own identity —
which carries the project through the label already. Two stores for one edge is
how a screen renders a width nobody set.
