## Context

The status table already refuses to know domain names: a column becomes filterable because its
values are categorical, which is a property of the values rather than of the name. That rule is
the one to extend, not to replace.

What forced this change is a reader's request — *show when this came from and who was in it* —
and the measurement underneath it:

| measured | where | consequence |
|---|---|---|
| `cellText` returns `''` for any object | `StatusTable.tsx:75-79` | a structured value contributes nothing to search |
| non-scalar columns are skipped for facets | `StatusTable.tsx:99` | a structured value cannot be filtered on |
| a facet is offered whenever distinct values ≤ 12 and ≤ half the rows | `:93-107` | a numeric column of near-unique values becomes a useless facet |

The first two make the producer's improvement a regression, which is why they come first.

## Goals / Non-Goals

**Goals:**

- A project can publish a structured value and have it be *more* usable, not less.
- Controls that fit what a column actually contains.
- A narrowed view that can be reloaded and handed over.
- Every one of these decided from values, never from names.

**Non-Goals:**

- **Parsing an identifier for domain content.** A slug that happens to embed a date is not mined
  for it — see D2.
- **A query language.** Filters compose; they do not become expressible as text a user must learn.
- **Server-side filtering or pagination.** These rows arrived in one answer; narrowing them is a
  view concern.
- **Anything that hides a failure.** See D5.

## Decisions

**D1 — A structured cell is indexed by its leaves and filtered by its sub-paths.**
`cellText` becomes a traversal: every scalar leaf inside the cell contributes to the free-text
index, joined so that a search for a participant's name matches the row that lists them. For
filtering, a sub-path becomes a candidate column in its own right (`source.kind`, `source.date`)
and is then subject to the same shape rules as any other column.

Rejected: rendering the object as JSON and searching the JSON text. It matches punctuation and
key names, so a search for `date` would match every row — a filter that cannot narrow, which is
the failure the facet bounds already exist to prevent.

**D2 — A date-shaped COLUMN is detected; a date inside an identifier is not.** The distinction is
the whole of the boundary and it is easy to lose. If every non-empty value of a column parses as a
date, the column is a date column and gets a period control. If a value is an identifier that
happens to contain a date — measured on a real answer, where three of five values embedded one and
two did not — nothing is extracted. A parser that works on some rows and silently fails on the rest
reports a narrowed set that is wrong in the reassuring direction: fewer rows, no error.

**D3 — Numeric columns get a range, and the categorical rule yields to it.** Where a column's
values are all numeric and its distinct count is high enough that a facet would be one-row chips,
the range replaces the facet. Both bounds already exist for the facet; this reuses them rather than
inventing a second notion of "too many values".

**D4 — Filter state lives in the URL, and an unreadable state is ignored rather than guessed.** A
malformed or stale parameter (a column that no longer exists, a value no project sends any more)
must not silently select nothing — that is indistinguishable from a project with no rows. The
state is applied where it still matches and what could not be applied is reported next to the row
count, in the same place the surface already says what a filter withheld.

**D5 — A hidden column may not conceal a failure, and this is the one rule that outranks the
comfort this change buys.** The surface already holds that compacting must never hide a failure.
Column visibility is compaction with a new name, so: a hidden column whose values include anything
the surface would otherwise mark must be counted where the reader is standing — beside the column
control, not only in the column that is no longer there.

**D6 — Per-column search narrows the same index, and states what it withheld.** It is the global
search restricted to one column, not a second mechanism. The row count keeps saying how many rows
are hidden and by what, because two independent narrowing controls make "why is this empty" harder,
not easier.

## Risks / Trade-offs

- **More controls is itself a way to make a surface unusable** → accepted with a constraint: a
  control appears only when the column's values make it useful, which is the same rule that stops
  a facet appearing for a column with one distinct value.
- **Indexing every leaf makes search match things the reader cannot see** → real, and the mitigation
  is that a matched row must show why it matched. A structured cell renders its leaves, so a match
  is visible in the row rather than hidden inside a collapsed object.
- **URL state can be pasted between projects** → D4 covers it: what cannot be applied is reported,
  never silently dropped.
- **A date column detected from values could be wrong for a column of numeric-looking strings** →
  the check is that every non-empty value parses, so one non-date value disqualifies the column. It
  fails toward the existing behaviour, which is the safe direction.
