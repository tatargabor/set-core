## Context

The strip is the fleet screen's answer to "where is this agent's work?" — resolved per
agent session from the openspec tree. The inference had one axis, recency; a busy
session's verify work breaks it.

## Decisions

- **The anchor lives in `resolve_stage`, not in the inference.** Recency stays the
  inference's order (existing tests and callers keep their contract); the anchor needs
  the TREE (`derive_position`), which the inference deliberately does not see.
- **Half the leader's tail weight is the ownership threshold.** Both measured cases sit
  far from the boundary: the live drive-by was 2 mentions against the leader's 2-3
  (weights comparable → anchor fires), the genuine-switch case 2000 against 4600
  (within 2× — recency decides, and it names the NEW change). Wait — the switch case's
  abandoned change derives to nothing in that test, so the anchor cannot fire there at
  all; the anchor only ever promotes a candidate that the TREE says is ARCHIVED. A
  false anchor requires a candidate that is archived in the tree AND heavier than half
  the leader — i.e. the session really did finish it.
- **Weights ride the existing memo.** One bounded read per record state, as before;
  the memo's payload widens from slugs to slugs+counts, which the confidentiality line
  already admits ("a count, a shape, or a path it declined to read").

## Risks / Trade-offs

- A session that archives its change and immediately starts sparse new work shows
  `archive` until the new work's mentions reach half the finished change's tail weight —
  understating progress briefly. Understating finished→done is the honest direction of
  the two; the current defect overstated done→working.

## Migration Plan

Additive; the declared path and all gap paths are untouched.

## Open Questions

- None.
