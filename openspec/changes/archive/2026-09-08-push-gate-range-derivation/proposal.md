## Why

The gate's verification pass (2026-09-08, live battery + 3 new unit tests against the unfixed code) measured two push-mode holes, both failing in the publish direction: the pre-push hook derived its range from `@{u}`, which is unset exactly on the FIRST push of a branch — the push that carries every commit — so a leaking HEAD pushed unscanned; and an unresolvable range made `git diff` fail into an empty stdout, which the scanner reported as a clean zero-file scan. A third live measurement found the PreToolUse gate's command regex blind to `git -c <key>=<value> commit` — an ordinary, non-malicious command shape — which created the very commit the gate exists to refuse.

## What Changes

- The installed `pre-push` hook derives its scan range from the refs the push actually publishes (the hook's stdin), not from `@{u}`: `remote_sha..local_sha` per pushed ref; a new remote ref (all-zero remote sha) scans from the merge-base with the nearest remote-tracking ref; only ref deletions publish nothing and pass.
- An unresolvable range now refuses blind (exit 2) instead of reporting a silent zero.
- A push with no derivable base (no upstream AND no common history with any remote) runs the whole-tree checks and ANNOUNCES that the env-marker check has no base — loud blindness, never a silent zero, and never the over-blocking alternative (this repository's tree legitimately carries identity-shaped documentation examples, so maximal scanning would false-block its own pushes).
- The PreToolUse gate's `PUBLISH_RX` consumes git's two-token option forms (`-c <k>=<v>`, `-C <path>`), so `git -c core.hooksPath=… commit` is gated exactly like plain `git commit`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `env-leak-gate`: the push (range) mode gains a range-derivation contract — what a push scans is what the push publishes; a range that cannot resolve refuses blind; a push with no base announces its env-marker blindness. The commit-time binding requirement gains the two-token git option forms.

## Impact

- `bin/set-leakscan` — pre-push hook template rewritten (stdin-derived ranges); range-mode resolve check; no-base announcement via the existing `env_marker_sources_missing` reporting path.
- `bin/set-hook-leakscan` — `PUBLISH_RX` alternative order.
- `tests/unit/test_leakscan.py` — 11 new tests (push range derivation, refuse-blind, announced blindness, publish-regex shapes).
- No consumer-project impact: the gate is deployed by `set-leakscan --install-hooks`, which writes the new template on its next run in each repository.
