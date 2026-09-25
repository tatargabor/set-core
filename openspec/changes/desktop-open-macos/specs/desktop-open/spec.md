## ADDED Requirements

### Requirement: The opener is the host platform's, not one platform's

The endpoint SHALL hand the path to the program that knows the file associations **of the
platform the framework is running on** — `open` on macOS, `xdg-open` on Linux and other
platforms — resolved on `PATH` at request time.

The endpoint SHALL NOT fall back from one platform's opener to another's. A platform whose
opener is absent SHALL be refused as it is today; a fallback would hand a path to a program
that means something different, and the refusal exists so that outcome is reported rather
than guessed at.

Choosing by platform is what makes the guard below meaningful: a refusal list is a claim about
what a *particular* desktop runs, so the platform that decides the opener and the platform
whose launcher classes are refused SHALL be the same one.

#### Scenario: A path is opened on macOS

- **WHEN** the framework runs on macOS and a person activates an absolute path naming an
  existing document
- **THEN** it is handed to `open`, and the answer states it was handed over

#### Scenario: A path is opened on Linux

- **WHEN** the framework runs on a non-macOS platform and a person activates such a path
- **THEN** it is handed to `xdg-open`, unchanged from before

#### Scenario: The platform's opener is missing

- **WHEN** the platform's own opener is not on `PATH`
- **THEN** the request is refused, the reason names **that platform's** opener, and no other
  program is tried

### Requirement: A macOS application bundle is a launcher, not a document

The endpoint SHALL refuse a path whose resolved target ends in `.app`, and SHALL do so by the
suffix rather than by any permission check.

This is stated separately because the general executable-bit rule cannot reach it: a `.app` is
a **directory**, and the bit rule deliberately exempts directories (every traversable directory
carries the bit, so a uniform check would refuse every folder). An application bundle is
therefore the one launcher class that a correct Linux-shaped guard waves through.

#### Scenario: An application bundle

- **WHEN** the activated path names a `.app` bundle
- **THEN** it is refused, nothing is started, and the reason says it is a launcher

#### Scenario: An ordinary directory still opens

- **WHEN** the activated path names a directory that is not a `.app`
- **THEN** it is handed over as before — refusing bundles SHALL NOT refuse folders

## MODIFIED Requirements

### Requirement: What must never be handed over

The endpoint SHALL refuse a path that the desktop would RUN rather than OPEN, and SHALL
refuse it before any handler is started. Refused are, at minimum:

- a path that is not absolute,
- a path that does not exist,
- a `.desktop` entry,
- a macOS `.app` bundle,
- a file whose association executes it or installs from it, including `.command`, `.terminal`
  and `.dmg` on macOS,
- any file carrying an executable bit.

The list SHALL be platform-complete for every platform the endpoint opens on, and each entry
SHALL rest on a measurement of what that platform's association actually does with the
suffix — never on plausibility. A suffix nothing is registered for on the measured machine
SHALL NOT be added on the strength of its name.

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

#### Scenario: A file the desktop executes or installs from

- **WHEN** the activated path names a file whose association runs it or installs from it —
  `.command`, `.terminal` and `.dmg` among them
- **THEN** it is refused whatever its permissions say, and the reason names the association
  rather than the permissions

#### Scenario: A path that is not there

- **WHEN** the activated path does not exist
- **THEN** it is refused with a reason naming that, and no handler is started

#### Scenario: A relative path

- **WHEN** the request carries a path that is not absolute
- **THEN** it is refused — the framework does not resolve it against a working directory the
  caller cannot see
