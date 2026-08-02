## 1. The declaration — core (`lib/set_orch/`)

- [x] 1.1 Read an optional `follow` envelope key into `StatusResult` as a tuple of bare field names, dropping anything not shaped like a field name, degrading to no followable fields rather than to no answer [REQ: a-project-declares-which-of-its-fields-carry-a-followable-path]
- [x] 1.2 Name the new field in the `StatusResult` docstring field list, so the mirror test that treats every backticked token there as a claimed field keeps passing [REQ: a-project-declares-which-of-its-fields-carry-a-followable-path]
- [x] 1.3 Add a walker that returns the follow-declared fields PRESENT in an answer's data, with their values — declaration says what to look for, data says what is there [REQ: a-project-declares-which-of-its-fields-carry-a-followable-path]
- [x] 1.4 Unit tests: declared+present, declared+absent, declared+null, undeclared field holding a path-like string, malformed `follow` value [REQ: a-project-declares-which-of-its-fields-carry-a-followable-path]

## 2. The gate — core

- [x] 2.1 Implement path resolution: join against the project root, resolve symlinks, refuse anything outside the root after resolution [REQ: a-followed-path-stays-inside-the-project-tree-after-symlink-resolution]
- [x] 2.2 Implement the live-answer check: re-run the named command and accept only a path that is currently the value of a follow-declared field [REQ: a-path-is-followed-only-if-the-projects-live-answer-still-names-it]
- [x] 2.3 Unit tests for the gate, including a symlink out of the tree and a `..` traversal, both built as real files in a tmp tree rather than mocked [REQ: a-followed-path-stays-inside-the-project-tree-after-symlink-resolution]
- [x] 2.4 Unit test: a readable file in the tree that no declared field names is refused [REQ: a-path-is-followed-only-if-the-projects-live-answer-still-names-it]

## 3. The stream — API (`lib/set_orch/api/`)

- [x] 3.1 Add the SSE route that follows an accepted path, opening read-only and seeking to the end before the first read [REQ: a-stream-starts-at-the-end-and-is-bounded-in-lines-and-in-rate]
- [x] 3.2 Enforce a line budget and a rate cap, emitting a withheld-count event rather than dropping lines silently [REQ: a-stream-starts-at-the-end-and-is-bounded-in-lines-and-in-rate]
- [x] 3.3 Close on every terminal condition — file gone, replaced, unreadable, no longer named — with an error class the client receives [REQ: a-stream-that-ends-says-why]
- [x] 3.4 Log shape only: counts and error classes, never a line's content; assert this in a test that greps the emitted records for streamed text [REQ: following-reads-and-set-core-persists-none-of-what-it-reads]
- [x] 3.5 Verify nothing is cached: the answer cache is not touched by a follow, and no file under set-core's control holds streamed content after a stream closes [REQ: following-reads-and-set-core-persists-none-of-what-it-reads]

## 4. The surface — web (`web/src/`)

- [x] 4.1 Read `follow` from the answer and expose the present follow-declared fields, mirroring how caveats are matched from the data [REQ: a-project-declares-which-of-its-fields-carry-a-followable-path]
- [x] 4.2 Offer a follow control beside a declared field that holds a path, and offer nothing where the field is absent, null, or undeclared [REQ: a-project-declares-which-of-its-fields-carry-a-followable-path]
- [x] 4.3 Build the panel: lines as they arrive, JSON lines rendered as the producer's own key/value pairs in their own order, non-JSON lines as text [REQ: the-panel-renders-lines-and-recognises-nothing-inside-them]
- [x] 4.4 Show a stream's end reason and any withheld count where the lines were arriving, never as silence [REQ: a-stream-that-ends-says-why]
- [x] 4.5 Web unit tests for the control's presence rules and for the renderer's key-agnosticism, including lines whose keys differ from one another [REQ: the-panel-renders-lines-and-recognises-nothing-inside-them]

## 5. Proof

- [x] 5.1 Mutation-test the gate: force it to accept any in-tree path and confirm the refusal tests fail; restore and re-verify the restore by grep, not by assumption [REQ: a-path-is-followed-only-if-the-projects-live-answer-still-names-it]
- [x] 5.2 Mutation-test the domain-freedom: make the surface recognise a field NAMED `log` and confirm the undeclared-field test fails [REQ: a-project-declares-which-of-its-fields-carry-a-followable-path]
- [x] 5.3 End-to-end against a domain-free probe project — a manifest plus a script that declares `follow` and writes a growing file — and LOOK at the panel, since structural counts prove it renders and say nothing about whether it is readable [REQ: the-panel-renders-lines-and-recognises-nothing-inside-them]
- [x] 5.4 Run the full web unit suite and the Python unit suite; compare failures against a baseline worktree rather than against a remembered count [REQ: following-reads-and-set-core-persists-none-of-what-it-reads]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN an answer declares `follow: ["log"]` and its data holds a `log` field with a path THEN the surface offers to follow that path, and the endpoint accepts it [REQ: a-project-declares-which-of-its-fields-carry-a-followable-path, scenario: a-declared-field-becomes-followable]
- [x] AC-2: WHEN an answer holds a field whose value looks exactly like a file path, and `follow` does not name it THEN no control is offered and the endpoint refuses the path [REQ: a-project-declares-which-of-its-fields-carry-a-followable-path, scenario: a-field-the-project-did-not-declare-is-not-followable]
- [x] AC-3: WHEN an answer carries a field named `log`, `logFile`, or `trace` and declares no `follow` THEN nothing is followable [REQ: a-project-declares-which-of-its-fields-carry-a-followable-path, scenario: the-framework-recognises-no-field-name-of-its-own]
- [x] AC-4: WHEN a declared field is absent, null, or empty because nothing is running THEN no control is offered and this is not reported as a failure [REQ: a-project-declares-which-of-its-fields-carry-a-followable-path, scenario: a-declared-field-holding-no-path-is-not-an-error]
- [x] AC-5: WHEN a client requests a path that was followable earlier but is absent from the current answer THEN the request is refused with a reason and no file is opened [REQ: a-path-is-followed-only-if-the-projects-live-answer-still-names-it, scenario: a-path-the-answer-no-longer-names-is-refused]
- [x] AC-6: WHEN a client requests a readable file in the project tree that no declared field names THEN the request is refused [REQ: a-path-is-followed-only-if-the-projects-live-answer-still-names-it, scenario: an-arbitrary-path-inside-the-project-is-refused]
- [x] AC-7: WHEN a declared path resolves through a symlink to a file outside the project root THEN the request is refused and nothing is read [REQ: a-followed-path-stays-inside-the-project-tree-after-symlink-resolution, scenario: a-symlink-pointing-outside-the-tree-is-refused]
- [x] AC-8: WHEN a requested path contains `..` segments that resolve outside the project root THEN the request is refused [REQ: a-followed-path-stays-inside-the-project-tree-after-symlink-resolution, scenario: a-traversal-segment-cannot-escape-the-root]
- [x] AC-9: WHEN a follow stream has run and closed THEN no file, cache entry, or log line under set-core's control contains any streamed content [REQ: following-reads-and-set-core-persists-none-of-what-it-reads, scenario: the-stream-leaves-nothing-behind]
- [x] AC-10: WHEN the endpoint logs about a stream THEN the entry carries counts and error classes and no text taken from the file [REQ: following-reads-and-set-core-persists-none-of-what-it-reads, scenario: a-diagnostic-records-the-shape-and-not-the-line]
- [x] AC-11: WHEN a client starts following a file that already holds many lines THEN it receives lines written after it connected [REQ: a-stream-starts-at-the-end-and-is-bounded-in-lines-and-in-rate, scenario: history-is-not-replayed-on-connect]
- [x] AC-12: WHEN the line budget or the rate cap is reached THEN the client is told what was withheld, where the lines were arriving [REQ: a-stream-starts-at-the-end-and-is-bounded-in-lines-and-in-rate, scenario: a-bound-is-stated-never-silent]
- [x] AC-13: WHEN the followed file is deleted or replaced while a client is following it THEN the stream closes carrying the reason [REQ: a-stream-that-ends-says-why, scenario: a-deleted-file-ends-the-stream-with-a-reason]
- [x] AC-14: WHEN the file becomes unreadable mid-stream THEN the client receives an error class and the stream closes [REQ: a-stream-that-ends-says-why, scenario: a-read-failure-is-reported-rather-than-swallowed]
- [x] AC-15: WHEN an arriving line parses as a JSON object THEN its keys are shown in the order the producer wrote them, none promoted [REQ: the-panel-renders-lines-and-recognises-nothing-inside-them, scenario: a-json-line-is-shown-by-its-own-keys]
- [x] AC-16: WHEN an arriving line is not valid JSON THEN it is rendered as text rather than dropped [REQ: the-panel-renders-lines-and-recognises-nothing-inside-them, scenario: a-non-json-line-is-still-shown]
- [x] AC-17: WHEN arriving lines carry different keys from one another THEN every line is rendered and no key is treated as required [REQ: the-panel-renders-lines-and-recognises-nothing-inside-them, scenario: a-missing-key-is-not-an-error]
