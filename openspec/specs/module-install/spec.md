# module-install Specification

## Purpose
TBD - created by archiving change module-install-writer. Update Purpose after archive.

## Requirements

### Requirement: A project's declaration is read as what it says, and absence is not emptiness

The system SHALL read what a project asks for from a project-owned file, and SHALL report the
absence of that file as absence rather than as an empty request.

"Has not adopted the mechanism" and "adopted it and wants nothing" are different states, and a
reader that takes the first for the second will report agreement with a project that never agreed
to anything. The distinction is carried on the value itself, not inferred by each caller.

An unreadable or malformed declaration SHALL be reported as absent rather than raising, because
this reader is consulted while rendering a list of many projects and one broken file must not
remove the others from the answer.

#### Scenario: A project that declared nothing
- **WHEN** the project has no declaration file
- **THEN** the result reports that no declaration is present, and no module is reported as wanted

#### Scenario: A project that declared an empty set
- **WHEN** the project has a declaration file that names no modules
- **THEN** the result reports that a declaration IS present, with no modules wanted

#### Scenario: A declaration that cannot be parsed
- **WHEN** the declaration file is not readable as its documented format
- **THEN** the result reports no declaration present, and the reader does not raise

### Requirement: What is installed is recorded, and the record is written only after the write

The system SHALL keep a project-local record of which modules are installed and at which version,
and SHALL write that record only after an install has actually written its files.

A record written first, or written on refusal, states that a module is installed when it is not —
and every later reader, including the version comparison and any screen built on it, believes it.
The record is the framework's own answer to "what did we put here", so it must never run ahead of
the act it describes.

#### Scenario: A successful install updates the record
- **WHEN** an install writes at least one file
- **THEN** the install record names that module at the version installed

#### Scenario: A refused install leaves the record alone
- **WHEN** an install is refused for a missing requirement
- **THEN** the install record is unchanged, and does not name the refused module

### Requirement: The files a module places are declared, and its executable part is never among them

The system SHALL derive the set of files an install writes from the module's own declaration, and
SHALL exclude any path the declaration marks as the module's executable part.

The exclusion SHALL be structural — a path declared executable never reaches the writer — rather
than a rule stated for the writer to honour. A module's code is installed by a package manager;
copying it into a project produces a second copy that drifts and that nothing upgrades.

A path declared BOTH as an installed file and as executable SHALL be excluded and reported, not
silently resolved in either direction.

#### Scenario: An executable path is not planned
- **WHEN** a module declares a path as its executable part
- **THEN** that path is absent from the planned file list

#### Scenario: A path declared as both is excluded and named
- **WHEN** a module declares one path both as an installed file and as executable
- **THEN** the path is excluded from the plan and the contradiction is reported

### Requirement: A version comparison never reports "cannot tell" as agreement

The system SHALL compare the version a project expects against the version installed, and SHALL
report three distinct outcomes: agreement, disagreement, and undeterminable.

An expectation that cannot be read on either side SHALL be undeterminable, never agreement. The
whole reason to ask is the case where the two differ; rendering "cannot tell" as "fine" removes
exactly that answer, and does so in the direction that reassures.

A project with no declaration SHALL yield no comparisons at all, rather than an empty set of
disagreements — a surface that renders "no mismatches" over a project that never declared anything
is reporting calm it did not verify.

#### Scenario: Expected and installed differ
- **WHEN** a project expects one version and another is installed
- **THEN** the comparison reports disagreement, naming both versions

#### Scenario: A module wanted but not installed
- **WHEN** a project expects a module that is not installed
- **THEN** the comparison reports undeterminable, and does not report agreement

#### Scenario: No declaration yields no comparisons
- **WHEN** the project has no declaration
- **THEN** no comparisons are produced

### Requirement: An install writes the module's declared files through the existing per-file deploy discipline

The system SHALL perform an install by writing each planned file through the same per-file writer
the framework already uses to deploy templates into a project, and SHALL NOT carry a second copier
of its own.

That writer already owns the hash ledger, the protected-file rule, the write-once rule, committed
deletions read as intent, and tombstones. Every one of those exists because a specific silent
overwrite reached a real repository. A parallel copier would not merely duplicate them, it would
have to be found and fixed separately the next time one of them is wrong.

The install SHALL be addressable per module: installing one module SHALL NOT write another
module's files.

#### Scenario: Declared files are written
- **WHEN** an install runs for a module in a project that has none of its files
- **THEN** each planned file is present in the project afterwards, and each is named in the report

#### Scenario: A file the project modified is not overwritten
- **WHEN** an install would write a protected file the project has edited
- **THEN** the file is left as the project has it, and the skip appears in the report with its reason

#### Scenario: Installing one module leaves another alone
- **WHEN** an install runs for one module in a project that has two installed
- **THEN** no file belonging only to the other module is written

### Requirement: A missing requirement is a refusal, before anything is written

The system SHALL refuse an install whose module declares a requirement the project does not have,
SHALL name the missing requirement in the refusal, and SHALL refuse before writing any file.

A refusal, not a warning. A warning is a thing a reader can click past, and the state it leads to
is a half-installed project nobody chose — files present, requirement absent, and nothing on the
project's side recording that the two do not go together.

Refusing after a partial write is the same failure with extra steps, so the requirement check
SHALL precede the first write rather than accompany it.

#### Scenario: A module whose requirement is absent
- **WHEN** an install is asked for a module that requires another the project does not have
- **THEN** the install is refused, the missing requirement is named, and no file is written

#### Scenario: The refusal precedes the first write
- **WHEN** an install is refused for a missing requirement
- **THEN** the project contains none of that module's files, including the first one in the plan

### Requirement: The install reports what it did NOT do, and says so when it changed nothing

The system SHALL return, for every install, the files written, every file skipped together with
the reason it was skipped, and an explicit statement when no file was written at all.

A silent skip is a defect of the same class as a silent overwrite: both leave a project in a state
its owner did not choose and cannot see. An install that left six files alone because the project
had edited them is a *good* outcome and a *misleading* answer unless it is said.

A run that wrote nothing SHALL state that outcome in its own right. Returning success with an
empty list is technically true and reads as "installed".

#### Scenario: Skips are named with reasons
- **WHEN** an install leaves files alone
- **THEN** each such file appears in the report with the reason it was skipped

#### Scenario: A run that wrote nothing says so
- **WHEN** an install writes no files
- **THEN** the report states that outcome explicitly, rather than reporting a plain success

#### Scenario: Both halves appear together
- **WHEN** an install writes some files and skips others
- **THEN** the report names both sets, and neither is inferable only from the other's absence
