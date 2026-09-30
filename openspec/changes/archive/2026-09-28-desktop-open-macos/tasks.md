## 1. The opener

- [x] 1.1 Replace the `_OPENER` constant with `_opener_name()` returning `open` on `darwin`
      and `xdg-open` otherwise, and resolve it on `PATH` inside the handler
      [REQ: the-opener-is-the-host-platforms-not-one-platforms]
- [x] 1.2 Keep the missing-opener refusal, with the message naming the platform's own opener —
      no fallback to the other platform's [REQ: the-opener-is-the-host-platforms-not-one-platforms]
- [x] 1.3 Update the module docstring and the `_OPENER` comment, which both state the
      Linux-only contract this change replaces
      [REQ: the-opener-is-the-host-platforms-not-one-platforms]

## 2. The macOS launcher classes

- [x] 2.1 Add `.app` to `_LAUNCHER_SUFFIXES`, with the measured UTI in the comment and the
      reason it cannot go through the executable-bit path
      [REQ: a-macos-application-bundle-is-a-launcher-not-a-document]
- [x] 2.2 Add `.command`, `.terminal`, `.dmg` to `_ASSOCIATION_RUNS`, each with its measured
      `kMDItemContentType` [REQ: what-must-never-be-handed-over]
- [x] 2.3 Record in the comment that `.workflow` was measured and deliberately NOT added
      [REQ: what-must-never-be-handed-over]

## 3. Tests

- [x] 3.1 Both opener branches, by patching `_opener_name()` — never by branching on the host
      platform, so each machine runs both
      [REQ: the-opener-is-the-host-platforms-not-one-platforms]
- [x] 3.2 The missing-opener refusal names the platform's own opener
      [REQ: the-opener-is-the-host-platforms-not-one-platforms]
- [x] 3.3 A real `.app` **directory** in `tmp_path` is refused, and an ordinary directory in
      the same test file still opens [REQ: a-macos-application-bundle-is-a-launcher-not-a-document]
- [x] 3.4 `.command`, `.terminal`, `.dmg` are refused with no executable bit set — the
      association, not the permissions [REQ: what-must-never-be-handed-over]
- [x] 3.5 Prove the new tests fail on unfixed source (stash-and-rerun), not only that they pass
      [REQ: what-must-never-be-handed-over]

## 4. Verify on the machine that reported it

- [x] 4.1 Restart `set-web` so the running process holds the fix, then activate a real PDF path
      from the fleet terminal and confirm it opens
      [REQ: the-opener-is-the-host-platforms-not-one-platforms]
- [x] 4.2 Run the desktop suite plus a set-diff against the pre-existing failure baseline
      [REQ: what-must-never-be-handed-over]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the framework runs on macOS and a person activates an absolute path naming an
      existing document THEN it is handed to `open`, and the answer states it was handed over
      [REQ: the-opener-is-the-host-platforms-not-one-platforms, scenario: a-path-is-opened-on-macos]
- [x] AC-2: WHEN the framework runs on a non-macOS platform and a person activates such a path
      THEN it is handed to `xdg-open`, unchanged from before
      [REQ: the-opener-is-the-host-platforms-not-one-platforms, scenario: a-path-is-opened-on-linux]
- [x] AC-3: WHEN the platform's own opener is not on `PATH` THEN the request is refused, the
      reason names that platform's opener, and no other program is tried
      [REQ: the-opener-is-the-host-platforms-not-one-platforms, scenario: the-platforms-opener-is-missing]
- [x] AC-4: WHEN the activated path names a `.app` bundle THEN it is refused, nothing is
      started, and the reason says it is a launcher
      [REQ: a-macos-application-bundle-is-a-launcher-not-a-document, scenario: an-application-bundle]
- [x] AC-5: WHEN the activated path names a directory that is not a `.app` THEN it is handed
      over as before
      [REQ: a-macos-application-bundle-is-a-launcher-not-a-document, scenario: an-ordinary-directory-still-opens]
- [x] AC-6: WHEN the activated path names a file with an executable bit set THEN it is refused,
      nothing is started, and the answer names the reason
      [REQ: what-must-never-be-handed-over, scenario: an-executable-file]
- [x] AC-7: WHEN the activated path names a `.desktop` file THEN it is refused, whatever its
      permissions are [REQ: what-must-never-be-handed-over, scenario: a-desktop-entry]
- [x] AC-8: WHEN the activated path names a file whose association runs it or installs from it
      — `.command`, `.terminal` and `.dmg` among them — THEN it is refused whatever its
      permissions say, and the reason names the association rather than the permissions
      [REQ: what-must-never-be-handed-over, scenario: a-file-the-desktop-executes-or-installs-from]
- [x] AC-9: WHEN the activated path does not exist THEN it is refused with a reason naming
      that, and no handler is started
      [REQ: what-must-never-be-handed-over, scenario: a-path-that-is-not-there]
- [x] AC-10: WHEN the request carries a path that is not absolute THEN it is refused
      [REQ: what-must-never-be-handed-over, scenario: a-relative-path]
