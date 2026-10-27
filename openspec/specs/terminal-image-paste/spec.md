# terminal-image-paste Specification

## Purpose
TBD - created by archiving change terminal-image-paste. Update Purpose after archive.

## Requirements

### Requirement: A pasted image reaches the agent as a path it can open

When the reader pastes an image into an agent terminal, the panel SHALL send the image to
the framework, and on success SHALL write the stored file's absolute path followed by a
single space into the pty. It SHALL NOT send a newline, and SHALL NOT submit anything on the
reader's behalf.

#### Scenario: An image is pasted into a focused terminal

- **WHEN** the reader pastes clipboard content whose types include an `image/*` entry
- **THEN** the image bytes are sent to the framework
- **AND** on success the terminal receives the stored file's absolute path followed by one space
- **AND** no newline or carriage return is written to the pty
- **AND** nothing else from the clipboard is written

#### Scenario: The reader decides when it is sent

- **WHEN** the path has been typed into the pty
- **THEN** the agent has not been asked to act
- **AND** the reader can keep typing, edit the line, or discard it exactly as with typed text

### Requirement: Text paste keeps its existing behaviour

A paste that carries text SHALL be handled as text, unchanged by this capability, including
a paste that carries both text and an image.

#### Scenario: A plain text paste

- **WHEN** the reader pastes content whose types are text only
- **THEN** the text reaches the pty exactly as it does today
- **AND** nothing is uploaded

#### Scenario: A paste carrying both text and an image

- **WHEN** the pasted content offers both a `text/plain` entry and an `image/*` entry
- **THEN** the text is used and the image is ignored
- **AND** nothing is uploaded

  The reason is stated so it is not "simplified" later: a rich-text copy from a browser or a
  document carries a screenshot of itself alongside the text far more often than a reader
  intends, and uploading on every such paste would send content nobody chose to send.

### Requirement: A failed paste is stated, never silent

When a pasted image cannot be stored, the panel SHALL say so where the reader is standing,
naming what went wrong, and SHALL write nothing into the pty.

#### Scenario: The framework refuses the image

- **WHEN** the upload is refused — too large, an unsupported type, or the store is full
- **THEN** the panel shows the refusal and the reason it was given
- **AND** the pty receives nothing at all

#### Scenario: The upload does not complete

- **WHEN** the upload fails or does not answer within its time limit
- **THEN** the panel says the image was not sent
- **AND** the pty receives nothing at all

  The success path is deliberately quiet — the typed path is its own receipt. The failure
  path is not, because a paste that silently does nothing leaves the reader believing the
  agent has a picture it does not have.

#### Scenario: While the image is on its way

- **WHEN** the upload has started and has not finished
- **THEN** the panel shows that a paste is in flight
- **AND** the terminal remains usable

### Requirement: Nothing about the pasted image is kept in the browser

The panel SHALL NOT persist the image, its bytes, its name or its stored path in any browser
storage, and SHALL NOT retain the bytes after the upload has been answered.

#### Scenario: After a paste

- **WHEN** an image has been pasted and the panel has finished with it
- **THEN** no `localStorage`, `sessionStorage`, IndexedDB or cache entry holds the image, its
  name, or its path
- **AND** reloading the screen recovers nothing about it
