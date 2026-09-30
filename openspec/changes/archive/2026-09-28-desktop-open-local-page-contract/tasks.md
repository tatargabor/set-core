# Tasks

**Everything below is done.** Tasks 1 and 2 document behaviour that shipped as direct commits
and is already covered by tests; task 3 is the one thing writing the spec found, and it is a
real behaviour change carrying its own evidence.

## 1. The local-page class (documentation of shipped behaviour)

- [x] 1.1 The class exists in code as `_ASSOCIATION_INTERPRETS`, refused before the executable
      bit and after the run-or-install list (`38a534c6`, `lib/set_orch/api/desktop.py`)
      [REQ: a-local-page-is-its-own-refusal-class]
- [x] 1.2 The reason names interpretation rather than execution, so a reader is not sent to
      inspect permissions [REQ: a-local-page-is-its-own-refusal-class]
- [x] 1.3 Covered by `test_a_local_page_that_can_read_this_machine_is_refused`
      [REQ: a-local-page-is-its-own-refusal-class]

## 2. The declaration that lifts it (documentation of shipped behaviour)

- [x] 2.1 `OpenRequest.viewed` → `refusal(allow_pages=...)`, lifting this class only
      (`55b961c2`) [REQ: a-caller-may-declare-the-page-is-already-open-and-that-lifts-this-class-alone]
- [x] 2.2 The file view sends it from its toolbar button; the terminal route does not send it
      at all (`web/src/components/FleetFileView.tsx`, `web/src/components/FleetTerminal.tsx`)
      [REQ: a-caller-may-declare-the-page-is-already-open-and-that-lifts-this-class-alone]
- [x] 2.3 Covered by `test_a_page_the_reader_has_open_is_handed_over_from_the_view`, which
      asserts a `.desktop`, a `.jar` and an executable stay refused with the flag set
      [REQ: a-caller-may-declare-the-page-is-already-open-and-that-lifts-this-class-alone]
- [x] 2.4 Verified live against a restarted server rather than by reading control flow: with
      the flag, `.html` handed over, `.app` and `.dmg` refused
      [REQ: a-caller-may-declare-the-page-is-already-open-and-that-lifts-this-class-alone]

## 3. `.svg` and `.svgz` join the class (the behaviour change)

- [x] 3.1 Measure, because the exclusion asked to be measured: sweep this machine's
      association table for every suffix the endpoint hands over. Result — Preview, VLC,
      Pages, Xcode, TextEdit for all of them, and **the browser** for `.svg` and `.svgz`
      [REQ: a-local-page-is-its-own-refusal-class]
- [x] 3.2 Add both to `_ASSOCIATION_INTERPRETS`, replacing the comment that excluded them with
      the measurement and the second reason the exclusion is stale — `viewed` did not exist
      when it was written [REQ: a-local-page-is-its-own-refusal-class]
- [x] 3.3 Move `diagram.svg` out of the "ordinary file is still handed over" list, which
      encoded the old contract [REQ: a-local-page-is-its-own-refusal-class]
- [x] 3.4 Two tests in its place: the refusal, and the `viewed` lift. Prove the first fails on
      unfixed source, and say in the second's docstring that it does NOT — it holds the
      boundary, not the change [REQ: a-local-page-is-its-own-refusal-class]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a person activates an absolute path naming a local page THEN it is refused,
      nothing is started, and the reason says it opens as a local page
      [REQ: a-local-page-is-its-own-refusal-class, scenario: a-local-page-is-refused-by-default]
- [x] AC-2: WHEN the activated path names an `.svg` or `.svgz` THEN it is refused as a local
      page, not handed over as an image
      [REQ: a-local-page-is-its-own-refusal-class, scenario: a-document-format-that-a-browser-renders-counts-as-one]
- [x] AC-3: WHEN the activated path names a document whose association opens a viewer or an
      editor THEN it is handed over as before
      [REQ: a-local-page-is-its-own-refusal-class, scenario: a-file-the-desktop-merely-displays-or-edits-is-not-one]
- [x] AC-4: WHEN the field is set and the path names a local page THEN it is handed to the
      platform's opener
      [REQ: a-caller-may-declare-the-page-is-already-open-and-that-lifts-this-class-alone, scenario: the-reader-hands-over-a-page-they-have-open]
- [x] AC-5: WHEN the field is set and the path names a `.app`, a run-or-install file, or an
      executable THEN it is refused exactly as without the field
      [REQ: a-caller-may-declare-the-page-is-already-open-and-that-lifts-this-class-alone, scenario: the-declaration-does-not-reach-the-other-refusals]
- [x] AC-6: WHEN a path is activated from a surface holding the path and not the contents THEN
      the field is absent and the local-page refusal applies
      [REQ: a-caller-may-declare-the-page-is-already-open-and-that-lifts-this-class-alone, scenario: a-path-that-was-only-named-is-not-a-page-the-reader-has-open]
