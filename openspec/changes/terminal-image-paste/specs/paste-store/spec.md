## IN SCOPE
- Where the framework puts binary content a reader pasted, and under what name.
- What it accepts: which types, and how large.
- What bounds the store, and when an entry stops existing.
- What must never be persisted or logged about it.

## OUT OF SCOPE
- The panel's behaviour around a paste — `terminal-image-paste` owns that.
- Reading, writing or listing a project's own files — `project-file-access` owns those, and
  this store is deliberately not part of it.
- Serving the stored content back to a browser. Nothing reads these files over HTTP; the
  agent reads them from disk.
- Any other kind of upload: attachments, avatars, artifacts, screenshots taken by the
  framework itself.

## ADDED Requirements

### Requirement: Pasted content is stored outside every project tree

The framework SHALL store pasted binary content under its own durable per-user data root,
and SHALL NOT write it into any project or worktree, at any path, under any option.

#### Scenario: An accepted image is stored

- **WHEN** an image is accepted
- **THEN** it is written under the framework's own per-user data root
- **AND** the response names the absolute path of the written file
- **AND** no path inside any known project root or worktree has been created or modified

#### Scenario: The store cannot be redirected into a project

- **WHEN** a request tries to influence where the file is written
- **THEN** the location is decided by the framework alone and the request's suggestion is ignored

  The reason this is a requirement rather than an implementation note: writing into a
  consumer's tree is the operation class the framework's safety work closed, and a store
  whose destination is negotiable reopens it through a different door.

### Requirement: The stored name is derived, never taken from the caller

The stored file's name SHALL be derived from the content and its type. A caller-supplied
file name SHALL NOT determine the stored name or any part of the path.

#### Scenario: A file name arrives with the content

- **WHEN** the upload carries a file name
- **THEN** the stored path does not contain it
- **AND** a name containing path separators, `..`, or control characters changes nothing about
  where the file lands

#### Scenario: The same image pasted twice

- **WHEN** identical bytes are stored twice
- **THEN** both requests answer with a usable path

### Requirement: Only images, and only within a bound

The store SHALL accept only image content, SHALL refuse anything larger than its declared
per-item limit, and SHALL state which rule refused it.

#### Scenario: An accepted type

- **WHEN** the content is one of the accepted image types
- **THEN** it is stored

#### Scenario: A refused type

- **WHEN** the content is not an accepted image type
- **THEN** it is refused with a message naming the type as the reason
- **AND** nothing is written

#### Scenario: Content over the size limit

- **WHEN** the content exceeds the per-item limit
- **THEN** it is refused with a message naming the limit and the size
- **AND** nothing is written

#### Scenario: The declared type and the bytes disagree

- **WHEN** the declared type says image and the bytes are not one
- **THEN** it is refused
- **AND** nothing is written

  A declared type is a claim by the caller. Trusting it would make the type check a
  statement about the request rather than about what landed on disk.

### Requirement: The store is bounded and its entries expire

The store SHALL enforce a total size ceiling and a maximum age, and SHALL remove entries that
exceed either. Removal SHALL NOT depend on a process having stayed alive.

#### Scenario: An entry outlives the maximum age

- **WHEN** a stored entry is older than the maximum age
- **THEN** it is removed the next time the store is used
- **AND** its absence is not reported as an error to anyone

#### Scenario: The store reaches its ceiling

- **WHEN** storing an item would take the store past its total ceiling
- **THEN** the oldest entries are removed until it fits
- **AND** if the item still does not fit, it is refused with the ceiling named

#### Scenario: The framework was not running

- **WHEN** the framework starts after a period during which it was stopped
- **THEN** expiry is applied from the entries on disk
- **AND** no entry survives merely because nothing was running when it should have expired

### Requirement: Nothing about the content is persisted or logged

The framework SHALL NOT persist pasted content anywhere but the store itself, and SHALL NOT
write the bytes, a caller-supplied name, or any content-derived text into a log, an error
message that leaves the machine, or any committed artifact. Only the SHAPE of the operation
may be logged.

#### Scenario: A stored image is logged

- **WHEN** an upload is stored
- **THEN** the log line carries the content type, the byte count and the outcome
- **AND** it carries neither the bytes, nor a caller-supplied name, nor the stored file name

#### Scenario: A refused image is logged

- **WHEN** an upload is refused
- **THEN** the log line names the rule that refused it
- **AND** carries nothing derived from the content

  A pasted image is a consumer's content, and the confidentiality boundary is persistence,
  not naming: the framework may hold it long enough for an agent to read it, and may keep no
  record of what it was.
