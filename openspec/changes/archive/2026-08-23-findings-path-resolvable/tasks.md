## 1. The resolution helper

- [x] 1.1 Create `lib/set_orch/finding_paths.py` with a module logger, the symbolic base
      constant (`repo-root`) and `resolve_finding_path(file, root)` returning a normalized
      absolute path, an unchanged-but-normalized already-absolute path, or `""` when either
      input is empty [REQ: a-declared-base-resolves-a-stored-path-to-an-absolute-one]
- [x] 1.2 Unit-test the helper: relative join, absolute passthrough, empty file, empty root,
      and a missing base defaulting to repo-root
      [REQ: a-declared-base-resolves-a-stored-path-to-an-absolute-one]

## 2. Declaring the base where the path is stored

- [x] 2.1 `_append_review_finding` (`lib/set_orch/verifier.py:235`) writes `path_base` into
      the JSONL entry [REQ: a-stored-finding-path-declares-its-base]
- [x] 2.2 `_write_review_findings_md` (`lib/set_orch/verifier.py:700`) emits a one-line base
      declaration in the file header block, only when the header is written
      [REQ: a-stored-finding-path-declares-its-base]
- [x] 2.3 `_read_existing_findings` (`lib/set_orch/verifier.py:655`) still parses a file that
      carries the new header line — the parser must not read it as a finding
      [REQ: a-stored-finding-path-declares-its-base]
- [x] 2.4 Test that neither artifact contains an absolute path, and that a stored `file`
      value and its fingerprint are byte-identical to the pre-change output
      [REQ: a-stored-finding-path-declares-its-base]

## 3. Resolving on the API surface

- [x] 3.1 `_read_review_findings` (`lib/set_orch/api/learnings.py`) adds `file_abs` to every
      issue, resolved from the project root, leaving `file` untouched
      [REQ: review-finding-responses-carry-a-resolved-absolute-path]
- [x] 3.2 The unified learnings endpoint's `review_findings` section carries `file_abs` on
      the same terms [REQ: review-finding-responses-carry-a-resolved-absolute-path]
- [x] 3.3 Test: issue with a relative file, issue with no file (empty `file_abs`, not the
      bare root), and an entry with no `path_base`
      [REQ: review-finding-responses-carry-a-resolved-absolute-path]

## 4. The dashboard

- [x] 4.1 `FindingRow` (`web/src/components/LearningsPanel.tsx:228`) renders `file_abs` when
      present, falling back to `file`; the path must not overflow its container
      [REQ: review-findings-section]
- [x] 4.2 Update the `file_abs` field in the web API types (`web/src/lib/api.ts`) and the
      affected component tests [REQ: review-findings-section]
- [x] 4.3 **Visual check in the browser** — open the dashboard's Learnings tab against the
      running server, expand a finding, and confirm the path shown is absolute and readable
      in its column. If the browser cannot be reached, this task stays OPEN and is stated as
      such in the commit [REQ: review-findings-section]

## 5. Regression evidence

- [x] 5.1 Stash-and-rerun each new test to prove it fails without the change
      [REQ: a-declared-base-resolves-a-stored-path-to-an-absolute-one]
- [x] 5.2 Run the Python unit suite and the web test suite; compare failures against a
      baseline actually run, not a remembered number
      [REQ: a-stored-finding-path-declares-its-base]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a review-findings JSONL entry is appended THEN it carries a field naming the
      symbolic base, and neither it nor any `issues[].file` is absolute
      [REQ: a-stored-finding-path-declares-its-base, scenario: jsonl-entry-carries-the-base]
- [x] AC-2: WHEN `.claude/review-findings.md` is created or appended to THEN it states once
      that its paths are relative to the repository root, and contains no absolute path
      [REQ: a-stored-finding-path-declares-its-base, scenario: the-committed-markdown-states-the-base]
- [x] AC-3: WHEN a finding is written with a relative file path THEN the stored `file` value
      and its fingerprint are unchanged
      [REQ: a-stored-finding-path-declares-its-base, scenario: stored-paths-are-unchanged]
- [x] AC-4: WHEN resolution is asked for a relative path and a root THEN it returns the
      normalized absolute join
      [REQ: a-declared-base-resolves-a-stored-path-to-an-absolute-one, scenario: relative-path-is-joined-to-the-root]
- [x] AC-5: WHEN resolution is asked for an already-absolute path THEN it returns it
      normalized, without joining the root
      [REQ: a-declared-base-resolves-a-stored-path-to-an-absolute-one, scenario: already-absolute-path-is-returned-unchanged]
- [x] AC-6: WHEN the path or the root is empty THEN resolution returns an empty string
      [REQ: a-declared-base-resolves-a-stored-path-to-an-absolute-one, scenario: nothing-to-resolve]
- [x] AC-7: WHEN a stored artifact carries no base declaration THEN resolution treats the
      base as the repository root
      [REQ: a-declared-base-resolves-a-stored-path-to-an-absolute-one, scenario: a-path-from-before-this-change]
- [x] AC-8: WHEN the review-findings endpoint returns an issue with a relative `file` THEN it
      also carries the absolute path, and `file` still holds the stored value
      [REQ: review-finding-responses-carry-a-resolved-absolute-path, scenario: issue-with-a-file-path]
- [x] AC-9: WHEN an issue has an empty or missing `file` THEN the resolved field is an empty
      string, not the project root
      [REQ: review-finding-responses-carry-a-resolved-absolute-path, scenario: issue-with-no-file-path]
- [x] AC-10: WHEN the unified learnings endpoint returns its `review_findings` section THEN
      its issues carry the resolved field on the same terms
      [REQ: review-finding-responses-carry-a-resolved-absolute-path, scenario: unified-learnings-endpoint]
- [x] AC-11: WHEN the user expands a finding row THEN the file path shown is the resolved
      absolute path
      [REQ: review-findings-section, scenario: expanded-finding]
- [x] AC-12: WHEN the API supplies no resolved path THEN the detail shows the stored relative
      path rather than an empty field
      [REQ: review-findings-section, scenario: expanded-finding-with-no-resolved-path]
