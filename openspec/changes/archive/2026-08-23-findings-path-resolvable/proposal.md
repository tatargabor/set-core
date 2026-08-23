## Why

A review finding names the file it is about with a **relative** path, and nothing anywhere
states what that path is relative to. The base is the writer's working directory — a
worktree that may since have been deleted — while the reader is somewhere else entirely.
The result is a reference that cannot be opened: click-to-open does nothing, `@`-completion
finds no file, the editor jumps nowhere. **Nothing errors and nothing warns**, so the cost
lands invisibly on whoever is reading the finding, every single time.

The fix is not to store absolute paths. Two constraints forbid that, and both were measured
rather than assumed:

- `Finding.fingerprint()` (`lib/set_orch/findings.py:60`) hashes the `file` field. Rewriting
  the stored value changes a finding's identity, which is what retry-convergence detection
  compares across iterations.
- `.claude/review-findings.md` is **committed** — `lib/set_orch/verifier.py:783` runs
  `git add` on it. An absolute `/home/<user>/…` path in a tracked file leaks the local
  username and directory layout, which the release-safety rule treats as a finding.

The pattern this change establishes is **store relative, display absolute**: the path and
the base it resolves against travel together, and only the surfaces that are not committed
render the joined result.

## What Changes

- **New**: a small path-resolution helper that joins a stored relative finding path to a
  declared base and returns an absolute path, and that leaves an already-absolute path
  untouched. It is the single place the join happens, so the two forms cannot drift.
- **Changed**: the review-findings JSONL entry (`_append_review_finding`,
  `lib/set_orch/verifier.py:235`) carries an explicit **symbolic** base field naming what
  its issue paths are relative to. Symbolic, not literal — no absolute path enters the file.
- **Changed**: `.claude/review-findings.md` (`_write_review_findings_md`,
  `lib/set_orch/verifier.py:700`) gains a one-line header stating that the paths below are
  relative to the repository root. The file stays free of absolute paths.
- **Changed**: the review-findings and learnings API responses
  (`lib/set_orch/api/learnings.py`) carry a resolved absolute path alongside each issue's
  stored relative one. The API knows the project path and its response is never committed,
  so this is where the join belongs.
- **Changed**: the dashboard's Learnings panel
  (`web/src/components/LearningsPanel.tsx:248`) shows the openable absolute path.
- **Unchanged, deliberately**: every stored `file` value, and therefore every fingerprint.

## Capabilities

### New Capabilities
- `finding-path-resolution`: how a finding's file path declares the base it resolves
  against, and how that base is joined into an absolute path for display. Owns the helper,
  the JSONL base field, and the review-findings.md header line.

### Modified Capabilities
- `learnings-api`: review-findings and learnings responses gain a resolved absolute path
  per issue.
- `learnings-web-panel`: the finding row displays the absolute path.

## Impact

- `lib/set_orch/verifier.py` — JSONL entry shape, review-findings.md header.
- `lib/set_orch/api/learnings.py` — response shape for review findings and learnings.
- `web/src/components/LearningsPanel.tsx` — finding row rendering.
- New module under `lib/set_orch/` for the resolution helper, plus unit tests.
- **Backward compatibility**: entries written before this change carry no base field.
  Readers must treat its absence as "repository root" rather than failing, otherwise every
  historical finding loses its path.
- **Not affected**: `Finding.fingerprint()`, retry-convergence detection, and the sentinel
  findings store (`lib/set_orch/sentinel/findings.py`), whose records carry no file path.
