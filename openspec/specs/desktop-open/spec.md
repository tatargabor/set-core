# desktop-open Specification

## Purpose
TBD - created by archiving change fleet-open-external-path. Update Purpose after archive.

## Requirements

### Requirement: One path can be handed to the desktop

The framework SHALL provide an endpoint that hands a single absolute path to the desktop's
default application for that path, and SHALL do so only in answer to a request a person's
activation produced. Nothing SHALL be opened by the framework on its own initiative.

The path is opened on the machine the framework runs on, and the answer SHALL make that
plain rather than leaving the reader to infer it from a file appearing on the wrong screen.

#### Scenario: An existing file is handed over

- **WHEN** a person activates an absolute path naming an existing regular file
- **THEN** the framework asks the desktop to open it with its default application, and
  answers that it was handed over

#### Scenario: An existing directory is handed over

- **WHEN** the activated path names an existing directory
- **THEN** it is handed over the same way, and the desktop's file manager is what opens

#### Scenario: Nothing opens without an activation

- **WHEN** a path appears anywhere the framework can read — terminal output, a log, a file
- **THEN** nothing is opened until a person activates it

### Requirement: What must never be handed over

The endpoint SHALL refuse a path that the desktop would RUN rather than OPEN, and SHALL
refuse it before any handler is started. Refused are, at minimum:

- a path that is not absolute,
- a path that does not exist,
- a `.desktop` entry,
- any file carrying an executable bit.

The reason this list exists is the direction it fails in: the text an activated path came
from was written by whatever an agent ran, so a wrong `open` is not a broken link, it is a
program starting. A refusal that lets one of these through is a hole; a refusal that stops an
ordinary file is an inconvenience. When the two are in tension the refusal wins.

#### Scenario: An executable file

- **WHEN** the activated path names a file with an executable bit set
- **THEN** it is refused, nothing is started, and the answer names the reason

#### Scenario: A desktop entry

- **WHEN** the activated path names a `.desktop` file
- **THEN** it is refused, whatever its permissions are

#### Scenario: A path that is not there

- **WHEN** the activated path does not exist
- **THEN** it is refused with a reason naming that, and no handler is started

#### Scenario: A relative path

- **WHEN** the request carries a path that is not absolute
- **THEN** it is refused — the framework does not resolve it against a working directory the
  caller cannot see

### Requirement: The endpoint reads nothing and persists nothing

The endpoint SHALL NOT read the content of the path it hands over, SHALL NOT copy it, and
SHALL NOT record it anywhere that outlives the request other than the framework's own
operational log. What it logs SHALL be the shape and the outcome — the path, whether it was
opened or refused, and the reason — and never file content.

#### Scenario: A file is opened

- **WHEN** a path is handed to the desktop
- **THEN** no content of that file is read by the framework and none is stored

### Requirement: A refusal is an answer, not a silence

Every outcome SHALL be reported to the caller: opened, or refused with a reason. A request
that fails because no desktop handler is available on this platform SHALL say so rather than
answering as if it had succeeded.

An opened-but-nothing-happened outcome is the failure this requirement exists to prevent: the
handler runs detached, so the endpoint answers on hand-over, and it SHALL NOT claim more than
that — it reports that the desktop was asked, never that a window appeared.

#### Scenario: No handler on this platform

- **WHEN** the machine has no desktop-open program available
- **THEN** the answer is a refusal naming that, not a success

#### Scenario: The answer is about hand-over

- **WHEN** the path is handed over successfully
- **THEN** the answer states that the desktop was asked to open it, and does not assert that
  an application window opened
