## REMOVED Requirements

### Requirement: One file's content can be read

**Reason**: Its scenario *"A binary file is refused rather than mangled"* asserts, **by name**,
the behaviour this change reverses — a renderable binary is now served rather than refused.
Rewriting that scenario's body while keeping its heading would leave the name contradicting
the check, which is the defect class this repository already refuses: the marker is what gets
counted, and a marker true of a narrower subject still lies. The requirement is therefore
removed and replaced by *"File content is served typed by its bytes"* below, which
keeps every other scenario intact.

**Migration**: reading a text file does not change — same content, same identity, same
confinement, same size cap, and the same refusal when the cap is exceeded. What changes is
what used to be a single blanket refusal: a binary whose media type the framework serves for
rendering now comes back as bytes with that type, and one it cannot render comes back as a
refusal that NAMES the type and size instead of saying only "not a text file". The write
endpoint, the identity check and every confinement rule are untouched.

## ADDED Requirements

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
