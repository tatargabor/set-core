## Context

A review finding stores its file path as whatever the reviewer emitted — a path relative to
the tree the gate ran in. That base is never written down. Everything downstream (the JSONL
log, the committed markdown, the API, the dashboard, and the agent quoting any of them into
a chat reply) inherits a path it cannot resolve, and the failure is silent: an unopenable
path looks exactly like an openable one until somebody clicks it.

Two hard constraints shape the fix, and both were measured rather than assumed:

- **`Finding.fingerprint()` hashes `file`** (`lib/set_orch/findings.py:60`). The fingerprint
  is how Tier 3 detects retry convergence, so rewriting the stored value silently changes
  finding identity across attempts.
- **`.claude/review-findings.md` is committed** — `lib/set_orch/verifier.py:783` runs
  `git add` on it. An absolute `/home/<user>/…` inside a tracked file is exactly what the
  release-safety rule scans for.

## Goals / Non-Goals

**Goals**
- A reader can open the file a finding names, from wherever they are standing.
- The base a stored path resolves against is written down beside the path, not inferred.
- One resolution function, so the stored and displayed forms cannot drift in one caller.

**Non-Goals**
- Changing any stored `file` value, or any fingerprint derived from one.
- Making the agent's prose correct — that is the `file-references` rule's job (`4843a0ff`),
  and it is an instruction, not a constraint. This change is the deterministic half.
- Verifying that a resolved path still exists on disk.

## Decisions

**Store relative, display absolute.** The alternative — storing absolute paths — was
rejected on both constraints above: it breaks fingerprints and it leaks local layout into
a committed file. Splitting the two forms costs one field and one function, and keeps every
persisted artifact portable.

**The base is symbolic, not literal.** The JSONL entry gains `path_base: "repo-root"` rather
than a literal root directory. A literal root is an absolute path, which is the thing the
release-safety rule forbids in artifacts that can be published, and it goes stale the moment
the tree is cloned or moved. A symbolic name is resolved by whoever reads it, against the
root they actually have.

**`repo-root`, not `worktree-root`.** Review paths are emitted relative to the tree the gate
ran in — a worktree — but a worktree and its host share the same file layout, and the
worktree is routinely deleted before anyone reads the finding. Naming the base `repo-root`
means a reader with only the main checkout resolves correctly, which is the common case.

**The resolution helper is a new module** (`lib/set_orch/finding_paths.py`), not an addition
to `findings.py`. `findings.py` is the gate-output extractor; the API layer needs the join
and nothing else, and should not import an extractor to get it.

**A missing `path_base` means `repo-root`.** Entries written before this change carry no
field. Treating the absence as an error would drop the path from every historical finding —
the fail direction that loses data — so absence resolves the same way the new default does.

**The API adds a field, it does not replace one.** `file` keeps its stored value and
`file_abs` carries the resolved one. Replacing `file` would break any consumer comparing it
against stored data, and would put an absolute path where callers expect a portable one.

## Risks / Trade-offs

- **Two fields for one fact can drift** → only one function ever produces `file_abs`, and it
  is never persisted; it is recomputed per response from the stored value.
- **A resolved path can point at a file that no longer exists** (worktree deleted, file
  renamed) → out of scope by design. An openable-looking path that 404s in the editor is
  still strictly better than one that resolves nowhere, and checking existence per finding
  would put a stat call in a hot response path.
- **The dashboard now shows a long absolute path in a narrow column** → the UI task is
  paired with a required visual check in the browser, per the ui-quality rule. A structural
  test cannot see a path that overflows its container.
- **A future caller stores `file_abs` by mistake** → the spec states the stored value is
  byte-identical to before, and a test asserts the fingerprint is unchanged.

## Migration Plan

No migration step and no data rewrite. New JSONL entries carry `path_base`; old ones do not
and resolve identically via the documented default. The markdown header appears on the next
append to any given file; existing files keep their content. Rollback is reverting the code —
the extra field is ignored by readers that do not know it.

## Open Questions

None blocking. Whether other finding surfaces (the MCP activity payload, CLI output) should
carry `file_abs` too is deliberately left out of this change: they are separate consumers,
and adding them without a reader that uses them would be dead fields.
