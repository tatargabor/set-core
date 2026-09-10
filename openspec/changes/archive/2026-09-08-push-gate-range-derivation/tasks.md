## 1. Push gate derives its range from the refs the push publishes

- [x] 1.1 Rewrite the installed `pre-push` hook template: per-ref `remote_sha..local_sha` from stdin; new remote ref scans from the merge-base with the nearest remote-tracking ref; deletion-only pushes pass; no stdin at all falls back to the whole-tree scan [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes]
- [x] 1.2 Live-verify the first-push hole is closed: leaking HEAD on a fresh branch with a bare origin → pre-push exits 1 with an `env-marker` BLOCKS finding [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes]
- [x] 1.3 Unit tests: first push scanned, ordinary push keeps its exact range, clean push passes, deletion-only publishes nothing [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes]

## 2. Refuse blind on an unresolvable range

- [x] 2.1 Range mode validates the range with `git rev-list -1` before scanning; unresolvable → exit 2, "refusing blind" naming the range [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes]
- [x] 2.2 Unit tests: unresolvable range exits 2; an empty-but-valid range (`HEAD..HEAD`) is still clean [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes]

## 3. No-base push announces its env-marker blindness

- [x] 3.1 When no range is derivable, append the blindness note to the scanner's `env_marker_sources_missing` reporting path (report + JSON); whole-tree checks still run and block [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes]
- [x] 3.2 Design alternative measured and rejected: maximal scanning (every line treated as added) false-blocks this repository's own no-upstream pushes on its legitimate member-name documentation examples (the same class as the clone-URL handle exemption) — announced blindness chosen instead [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes]
- [x] 3.3 Unit test: no common history with any remote → whole-tree checks run, "blind for this push" announced [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes]

## 4. PreToolUse gate sees git's two-token option forms

- [x] 4.1 `PUBLISH_RX` gains `-c <k>=<v>` and `-C <path>` alternatives, ordered before the bare-flag forms; bypass measured live before the fix (the command created the commit the gate exists to refuse) [REQ: Both actors are bound at commit time]
- [x] 4.2 Unit tests: end-to-end block for `git -c core.hooksPath=/dev/null commit` with leaking staged content; regex-level class covering two-token forms, single-token forms, and non-publishing commands [REQ: Both actors are bound at commit time]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a push range contains no added env-marker lines while the wider tree does THEN the push is not refused by the env-marker category [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes, scenario: old-contamination-does-not-block-a-clean-push]
- [x] AC-2: WHEN a branch is pushed whose remote-side ref does not exist yet THEN the scan covers the commits unique to the local side and refuses a leaking HEAD [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes, scenario: the-first-push-of-a-branch-is-scanned]
- [x] AC-3: WHEN a range names a ref that does not resolve THEN the scan exits 2 with a refusal naming the range [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes, scenario: an-unresolvable-range-refuses-blind]
- [x] AC-4: WHEN a push has neither an upstream range nor a common history with any remote THEN whole-tree checks run and the report states the env-marker blindness [REQ: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes, scenario: a-push-with-no-derivable-base-announces-its-blindness]
- [x] AC-5: WHEN a session runs `git -c <key>=<value> commit` whose staged content carries an env-marker THEN the PreToolUse gate blocks before git runs [REQ: Both actors are bound at commit time, scenario: a-commit-behind-a-config-override-is-still-gated]
