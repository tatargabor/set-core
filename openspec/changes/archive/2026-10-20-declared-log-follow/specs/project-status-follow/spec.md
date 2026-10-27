## IN SCOPE
- A project declaring which of its own fields carry a followable file path
- A streaming endpoint that emits new lines of such a file as they are written
- The gate deciding whether a requested path may be followed at all
- A surface control offered beside a declared field, and a panel that renders arriving lines

## OUT OF SCOPE
- Searching, filtering, or interpreting the contents of the followed file
- Writing to, rotating, or truncating the file
- Following a file on another machine (same-machine is the premise of this capability)
- set-core's own orchestration log panel, which reads set-core's logs and not a contract answer

## ADDED Requirements

### Requirement: A project declares which of its fields carry a followable path

The envelope MAY carry a `follow` key listing **bare field names**. A field named there, found at
any depth of `data`, is understood to hold a path to a file the project is writing. The framework
SHALL NOT recognise any field by its name for this purpose, and SHALL NOT offer to follow a field
that is not declared.

Bare names, matched at any depth, is the selector `caveats` already uses. A second, differently
shaped selector in the same envelope — a dotted path, say — is how a producer ends up guessing which
rule applies to which key, and a mis-shaped key fails silently: it matches nothing, and the surface
shows no control while the declaration looks correct.

#### Scenario: A declared field becomes followable
- **WHEN** an answer declares `follow: ["log"]` and its data holds a `log` field with a path
- **THEN** the surface offers to follow that path, and the endpoint accepts it

#### Scenario: A field the project did not declare is not followable
- **WHEN** an answer holds a field whose value looks exactly like a file path, and `follow` does
  not name it
- **THEN** no control is offered and the endpoint refuses the path

#### Scenario: The framework recognises no field name of its own
- **WHEN** an answer carries a field named `log`, `logFile`, or `trace` and declares no `follow`
- **THEN** nothing is followable, because the name is the project's word and not the framework's

#### Scenario: A declared field holding no path is not an error
- **WHEN** a declared field is absent, null, or empty because nothing is running
- **THEN** no control is offered, and this is reported as nothing to follow rather than as a failure

### Requirement: A path is followed only if the project's live answer still names it

Before opening any file, the endpoint SHALL re-ask the project for the command the path came from
and SHALL verify that the requested path is **currently** the value of a follow-declared field in
that answer. A path that is not SHALL be refused.

The alternative — accepting any path inside the project tree — turns a status endpoint into a
general file reader for the whole tree, and leaves the only check that would have stopped it in the
hands of the caller. The gate belongs where the effect is. Re-asking costs one command run, measured
at roughly a tenth of a second, and happens once per stream rather than once per line.

#### Scenario: A path the answer no longer names is refused
- **WHEN** a client requests a path that was followable earlier but is absent from the current answer
- **THEN** the request is refused with a reason, and no file is opened

#### Scenario: An arbitrary path inside the project is refused
- **WHEN** a client requests a readable file in the project tree that no declared field names
- **THEN** the request is refused, whatever the file is

### Requirement: A followed path stays inside the project tree after symlink resolution

The endpoint SHALL resolve the requested path to its real location and SHALL refuse it if the result
is outside the project's root. The check SHALL be applied to the resolved path, never to the string
as given.

A declared path is data arriving from outside the framework. A symlink is exactly how "inside the
tree" stops being true while the string still looks correct, which makes a string-only check
reassuring and wrong.

#### Scenario: A symlink pointing outside the tree is refused
- **WHEN** a declared path resolves through a symlink to a file outside the project root
- **THEN** the request is refused and nothing is read

#### Scenario: A traversal segment cannot escape the root
- **WHEN** a requested path contains `..` segments that resolve outside the project root
- **THEN** the request is refused

### Requirement: Following reads, and set-core persists none of what it reads

The endpoint SHALL open the file for reading only and SHALL NOT write, truncate, rotate, or delete
it. Lines SHALL be streamed to the client and held nowhere else: not in a cache, not in a log file,
not in this repository. Diagnostic logging for this path SHALL record shape only — byte counts, line
counts, error classes — and never content.

An agent's log is the densest domain source a project has: records, names, and business rules quoted
verbatim. The contract's existing rule that set-core persists nothing derived from a project's data
applies here at its sharpest.

#### Scenario: The stream leaves nothing behind
- **WHEN** a follow stream has run and closed
- **THEN** no file, cache entry, or log line under set-core's control contains any streamed content

#### Scenario: A diagnostic records the shape and not the line
- **WHEN** the endpoint logs about a stream
- **THEN** the entry carries counts and error classes, and no text taken from the file

### Requirement: A stream starts at the end, and is bounded in lines and in rate

The stream SHALL begin at the current end of the file rather than replaying its history, and SHALL
enforce a maximum number of lines and a maximum rate. Reaching a bound SHALL be reported to the
client rather than silently dropping lines.

Following is about now. Replaying a file that has grown to hundreds of kilobytes pushes the
interesting line off the screen before anyone reads it, and an unbounded stream is a denial of
service the framework built for itself.

#### Scenario: History is not replayed on connect
- **WHEN** a client starts following a file that already holds many lines
- **THEN** it receives lines written after it connected, not the file's existing content

#### Scenario: A bound is stated, never silent
- **WHEN** the line budget or the rate cap is reached
- **THEN** the client is told what was withheld, in the same place the lines were arriving

### Requirement: A stream that ends says why

Every termination — the file disappearing, being replaced, the project's answer no longer naming it,
or a read error — SHALL close the stream with a stated reason delivered to the client. A stream
SHALL NOT end silently.

A dead follow and a quiet file look identical from the outside. Silence is the one report that
cannot be acted on, and it is the report a reader is most likely to mistake for calm.

#### Scenario: A deleted file ends the stream with a reason
- **WHEN** the followed file is deleted or replaced while a client is following it
- **THEN** the stream closes carrying the reason, rather than hanging open

#### Scenario: A read failure is reported rather than swallowed
- **WHEN** the file becomes unreadable mid-stream
- **THEN** the client receives an error class and the stream closes

### Requirement: The panel renders lines and recognises nothing inside them

The surface SHALL render each arriving line as it came, showing a line that parses as JSON as its
key/value pairs in the producer's own key order, and any other line as text. It SHALL NOT promote,
colour, reorder, or specially position any key, and SHALL NOT require any particular key to exist.

Recognising a key inside a line is the same mistake as recognising a field name outside it, one
layer down: JSONL conventions differ per producer, and a panel built around one project's keys stops
working for the next one.

#### Scenario: A JSON line is shown by its own keys
- **WHEN** an arriving line parses as a JSON object
- **THEN** its keys are shown in the order the producer wrote them, none of them promoted

#### Scenario: A non-JSON line is still shown
- **WHEN** an arriving line is not valid JSON
- **THEN** it is rendered as text rather than dropped

#### Scenario: A missing key is not an error
- **WHEN** arriving lines carry different keys from one another
- **THEN** every line is rendered, and no key is treated as required
