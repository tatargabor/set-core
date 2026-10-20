# Project File Access Specification

## Purpose

Owns the endpoints a file view reads and writes through: listing a registered project's
files, reading one, writing it back only if it has not changed underneath, and confining
every path to a known project root while persisting nothing that was read.

## IN SCOPE
- Listing the files of a registered project over HTTP.
- Reading the text content of one file of a registered project.
- Writing new content back to one file of a registered project.
- The path guard that confines every one of those to a known project root.
- The size, count and type limits, and the requirement that each is STATED rather than
  applied silently.
- The conflict answer when the file changed underneath the caller between read and write.
- The confidentiality rule: the framework persists nothing it read.

## OUT OF SCOPE
- Any UI. What a panel shows and how it behaves belongs to `fleet-file-view`.
- Git history, blame, diff against a ref, or staging — reading and writing the working
  tree only.
- Creating, renaming, moving or deleting files; creating directories.
- Editing files outside a registered project (the framework's own installed files, a
  worktree of another project, anything under a home directory).
- Concurrent-edit merging. A changed file is refused, never merged.
- Authentication and who may call the API — the dashboard's existing binding decides that.

## Requirements

### Requirement: A project's files can be listed

The framework SHALL provide an endpoint that lists the files of a project the fleet screen
knows, identified the same way the fleet API's other guarded endpoints identify one — by its
root, checked against the set the screen itself is built from.

*Measured 2026-08-22, which is why it is the root and not the registry name:* of the projects
on the screen, `set-core` and `consumer-app` are in `~/.config/set-core/projects.json` and two
others are not — they reach the screen through process discovery and the messaging registry.
Resolving by registry name would therefore refuse a project the reader is looking at, which is
the divergence `fleet.py:660-673` already warns about in its own words: the rule is *what the
screen shows*, so the guard follows that list rather than deciding on its own what ought to be
in it.

The listing SHALL exclude what the project's own ignore rules exclude, and SHALL include
files that exist but are not yet tracked — a file an agent just wrote is exactly the file a reader wants to open.

#### Scenario: The listing follows the project's own ignore rules

- **WHEN** a project's files are listed and the project ignores a directory of build output
- **THEN** no file from that directory appears in the listing, and a file that is present in
  the working tree but not yet committed does appear

#### Scenario: A truncated listing SAYS it is truncated

- **WHEN** a project holds more files than the endpoint's cap
- **THEN** the answer carries both the returned entries and the fact that it was cut, with
  the cap and the true count, so no caller can read a short list as a complete one

#### Scenario: A root the screen does not know is refused

- **WHEN** the listing is asked for a root that is not one of the roots the fleet screen is
  built from
- **THEN** the endpoint refuses, and says nothing about what does exist on the machine

### Requirement: A file is written back only if it has not changed underneath

The write endpoint SHALL require the content identity the caller last read, and SHALL refuse
the write when the file on disk no longer matches it. A refused write SHALL leave the file
untouched and SHALL tell the caller that the file changed.

#### Scenario: The file is unchanged since it was read

- **WHEN** a write arrives carrying the identity that still matches the file on disk
- **THEN** the new content is written and the endpoint answers with the identity of what was
  just written

#### Scenario: An agent changed the file while it was open

- **WHEN** a write arrives carrying an identity that no longer matches the file on disk
- **THEN** the endpoint refuses the write, the file keeps the content the other writer gave
  it, and the answer says the file changed — this is the ordinary case on this screen, where
  an agent is editing the same tree

#### Scenario: A write to a file that has since been deleted

- **WHEN** a write arrives for a path that no longer exists
- **THEN** the endpoint refuses rather than recreating the file, because a deletion is an act
  by somebody and re-creating it would silently undo it

### Requirement: Every path is confined to a known project root

Before any read or write, the framework SHALL resolve the requested path to its real location
on disk — following symbolic links — and SHALL refuse it unless the result lies inside the
root of a registered project. A path that escapes SHALL be refused with the same answer
whether or not anything exists there.

#### Scenario: A traversal out of the project is refused

- **WHEN** a request names a path that climbs out of the project root
- **THEN** the request is refused with an access error and nothing is read or written

#### Scenario: A symbolic link pointing outside the project is refused

- **WHEN** the requested path is, or lies under, a link whose real target is outside every
  registered project root
- **THEN** the request is refused — the check is made on the RESOLVED path, because a link is
  exactly how a confined path reaches an unconfined place

#### Scenario: The refusal does not answer whether the file exists

- **WHEN** a path outside every known root is requested
- **THEN** the answer is the same for a path that exists and one that does not, so the
  endpoint cannot be used to probe the filesystem

### Requirement: The framework persists nothing it read

A project's source is the project's own domain, and this endpoint exists to display it, not
to accumulate it. The framework SHALL NOT write file content, or anything derived from it,
into any cache, index, log, event, error report or artifact. Diagnostics SHALL carry the
shape of a path — the project, the extension, the size — and never the content.

#### Scenario: A failure is logged without the content

- **WHEN** a read or write fails and the framework logs the failure
- **THEN** the log line carries the project and the reason, and no line of the file

#### Scenario: Nothing is cached between requests

- **WHEN** the same file is read twice
- **THEN** the second answer is read from disk, and no copy of the first is held anywhere in
  the framework

### Requirement: File content is served typed by its bytes

The framework SHALL provide an endpoint returning the content of one file of a checkout it
serves, together with an identity for the exact bytes it returned. That identity SHALL be
what a later write is checked against.

The answer SHALL be typed, and the type SHALL be decided by the BYTES, never by the file's
name or its permission bits:

- content that decodes as UTF-8 is served as text, as today;
- content that does not is served as bytes, with the media type the framework determined for
  it, so a caller can render it;
- a file the framework can neither decode nor classify as renderable is refused with a reason
  naming its media type and its size.

**Bytes SHALL be served in a form the browser will not itself render.** The response SHALL
carry `X-Content-Type-Options: nosniff` and a `Content-Disposition` that marks it as an
attachment, and the media type SHALL be checked against an allow-list of non-executing types
before the bytes are served at all. A dashboard has one origin, holding its own terminals and
its write endpoint; the isolation a second origin would give — the reason GitHub serves user
content from a separate domain entirely — is not available locally, so the substitute is that
nothing the endpoint returns is ever handed to the browser as something to interpret.

**The executable bit SHALL NOT be consulted.** Reading a file returns its bytes and starts
nothing, so a shell script is text like any other text. The guard that refuses to *run* a
file belongs to the desktop hand-over route, which this endpoint is not.

Extension SHALL NOT be the classifier for text. A `Makefile`, a `.env`, and a script with a
shebang and no suffix are all text, and a `.md` file may hold bytes that are not; the decode
attempt is the only test that answers for the file actually on disk.

The size cap and the type answer are SEPARATE refusals, and the answer SHALL say which one
fired. A reader told *not a text file* about a file that was merely too large will go looking
for the wrong problem.

#### Scenario: A text file is returned with its identity

- **WHEN** a readable text file inside a checkout the endpoint serves is requested
- **THEN** the endpoint returns its content and a content identity computed from those bytes

#### Scenario: A text file carrying an executable bit

- **WHEN** the requested file decodes as UTF-8 and has an executable bit set
- **THEN** it is returned as text exactly as any other text file, and the executable bit
  changes nothing about the answer

#### Scenario: A text file with no extension

- **WHEN** the requested file has no suffix, or a suffix the framework does not know, and its
  bytes decode as UTF-8
- **THEN** it is returned as text

#### Scenario: A renderable binary is served as bytes

- **WHEN** the requested file does not decode as text and its media type is one the framework
  serves for rendering
- **THEN** the endpoint returns its bytes with that media type, and does not attempt a lossy
  decode

#### Scenario: The bytes are not served as something to render

- **WHEN** any byte response is served
- **THEN** it carries `nosniff` and an attachment disposition, so the browser will not
  interpret the body on its own

#### Scenario: A media type off the allow-list

- **WHEN** the determined media type is not one of the non-executing types the endpoint
  serves
- **THEN** no bytes are served at all, and the answer is the naming refusal

#### Scenario: A binary that cannot be rendered names its type

- **WHEN** the requested file is neither decodable text nor of a media type the framework
  serves for rendering
- **THEN** the endpoint refuses with a reason naming the media type and the size, so the
  caller can say what the file is rather than only that it is not text, and returns no
  partial content

#### Scenario: A file too large to serve is refused with its size

- **WHEN** the requested file is larger than the endpoint's cap
- **THEN** the endpoint refuses and states the file's size and the cap, rather than returning
  a silently truncated prefix — and the refusal is distinguishable from the type refusal

#### Scenario: The confinement is unchanged

- **WHEN** any of these answers is served
- **THEN** the path was resolved and confined to a checkout the endpoint serves first, by the
  same verdict and with the same refusal as before this change
