## Why

set-core gained its largest new capability on 2026-07-24 — the ability to read a
consumer project's own development status through a published contract, and show it —
and **none of it is specified**. Measured before writing this: 81 commits that day,
zero through an OpenSpec change, and zero capability specs mentioning `contractVersion`,
`.set-endpoint.json`, or the status surface.

That is a knowledge-location problem, not a process complaint. What the surface DOES
currently lives in commit messages, in a living record that is a *decision log* (it
records why, not what), and in module docstrings. A session resuming after a compact
inherits prose and has to re-derive behaviour from code. The reason OpenSpec was adopted
in this repo in the first place was that set-core's accumulated knowledge had outgrown
what simple agent operations could carry — and this capability is exactly that shape.

**This proposal implements nothing.** It documents behaviour already shipped and already
enforced by tests, so that the specs describe the system as it is.

## What Changes

Three capability specs, split along the layers the code already has:

1. **`project-status-contract`** — the Layer 1 reader: envelope validation, declaration
   discovery (manifest and operator config), the read/write namespace split, per-command
   timeouts, and the `errorClass` vocabulary this side emits when it cannot get an answer.
2. **`project-status-api`** — the transport: which commands a page load may run, what may
   never reach `subprocess`, the in-memory-only answer cache, and the write path.
3. **`project-status-surface`** — the renderer: shape-driven rendering, the honesty rules
   (unknown is not zero, nothing is promoted, a gap renders as a gap), and the
   declaration-driven mechanisms a project uses to rank and emphasise its own data.

No code changes. Tasks are marked done with the commits that shipped them.

## Impact

- Affected specs: three new capabilities, all additive.
- Affected code: none. Every requirement below is already implemented and test-covered.
- **Going forward:** new capability work and contract changes go through OpenSpec; a
  measured defect fix does not, unless it changes contract behaviour — in which case it
  carries a spec delta.
