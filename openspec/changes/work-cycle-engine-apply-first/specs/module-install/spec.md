## IN SCOPE
- Splitting a module into what stays global and what a project must own
- A module declaring what it installs, what it needs, and which version it is
- Installing modules a project asked for, and not installing the ones it did not
- Deciding per file from recorded provenance, so a project's edits survive
- Saying out loud what was skipped and why — silence is not an outcome
- Deletion staying deleted
- Refusing to replace a generated artifact with an older generator's output

## OUT OF SCOPE
- What any particular module contains
- Rendering the install surface
- Removing an installed module from a project
- Deploying anything to a production environment

## ADDED Requirements

### Requirement: Only what a project must own is placed in the project
A module SHALL be split into an executable part, which the framework installs once per machine and
runs from there, and a project-owned part, which is placed in the project. The executable part SHALL
NOT be copied into a project. The project-owned part SHALL be limited to what the project decides or
edits: its declaration of which modules and versions it wants, its configuration, and files an agent
reads from the project itself.

#### Scenario: The executable part is not copied
- **WHEN** a module is installed into a project
- **THEN** the module's executable part is not placed in that project
- **AND** the project invokes it from the machine-wide installation

#### Scenario: The project-owned part is placed
- **WHEN** a module is installed into a project
- **THEN** its declaration and configuration are placed in the project

#### Scenario: Runtime state is not an install artifact
- **WHEN** a module writes run state, locks or pending answers while working
- **THEN** those are not treated as installed files
- **AND** an install neither creates nor removes them

### Requirement: A project states the version it expects, and a mismatch is reported
A project's declaration SHALL state the version of each module it expects. Where the version
installed machine-wide differs from what a project expects, the framework SHALL report the
difference. Where either version cannot be determined, the framework SHALL report it as unknown
rather than assuming they match.

#### Scenario: Machine-wide version differs from the project's expectation
- **WHEN** a project expects one version and another is installed machine-wide
- **THEN** the difference is reported, naming both

#### Scenario: Version cannot be determined
- **WHEN** either version cannot be read
- **THEN** the framework reports it as unknown
- **AND** it does NOT report the versions as matching

### Requirement: A module declares itself, and an incomplete declaration is refused
A module SHALL declare the files it installs, the modules it requires, and its own version. Each
declared file SHALL state how it is to be treated on a later install. A declaration carrying a file
with no treatment stated SHALL be **refused at validation time**, not defaulted.

#### Scenario: A file entry with no treatment stated
- **WHEN** a module declares a file without stating how later installs must treat it
- **THEN** validation fails and names that file
- **AND** the install does not proceed with a guessed treatment

#### Scenario: A complete declaration validates
- **WHEN** every declared file states its treatment
- **THEN** validation passes

### Requirement: A declared guard that does not take effect is an error
Every guard a module declares SHALL be enforced by the installer. Where a declaration names a guard
the installer does not implement or cannot apply, the install SHALL fail rather than proceed with the
guard silently absent.

#### Scenario: Unknown guard named
- **WHEN** a module declares a guard the installer does not recognise
- **THEN** the install fails and names the unrecognised guard

#### Scenario: A guard that cannot be applied
- **WHEN** a declared guard cannot be applied to a file
- **THEN** the install fails for that file rather than installing it unguarded

### Requirement: Every file decision comes from recorded provenance
The installer SHALL decide each file from the hash recorded when that file was last installed. A file
whose current hash matches what was recorded MAY be updated; a file whose hash differs belongs to the
project and SHALL be left alone; a file whose provenance is unknown SHALL be left alone.

#### Scenario: The project edited an installed file
- **WHEN** a file's current content differs from what was recorded at install
- **THEN** the installer leaves it alone

#### Scenario: An untouched file may be updated
- **WHEN** a file's current content matches what was recorded at install
- **THEN** the installer may update it

#### Scenario: Unknown provenance is not overwritten
- **WHEN** a file exists at a destination the installer has no record for
- **THEN** the installer leaves it alone

#### Scenario: A seed-time decision does not stand in for a hash
- **WHEN** a file was identical to its template when first installed and has since diverged
- **THEN** the installer detects the divergence from the recorded hash
- **AND** the fact that it was once identical does not authorise an update

### Requirement: A skip is reported, never silent
The installer SHALL report every file it did not install and why. A silent skip SHALL be treated as
a defect of the same class as a silent overwrite.

#### Scenario: Skipped files are listed
- **WHEN** an install leaves files alone because the project modified them
- **THEN** each is named in the install's output with its reason

#### Scenario: A run that changed nothing says so
- **WHEN** an install writes no files
- **THEN** it reports that outcome explicitly rather than exiting quietly

### Requirement: Deletion is durable
When a project removes a file the installer previously installed, that removal SHALL be recorded and
SHALL survive later installs. A recorded removal SHALL NOT be undone by installing again.

#### Scenario: A removed file stays removed
- **WHEN** a project deletes a previously installed file and the module is installed again
- **THEN** the file is not recreated

#### Scenario: Removals are inspectable
- **WHEN** a project's install record is read
- **THEN** the recorded removals can be listed

### Requirement: A generated artifact is never replaced by an older generator's output
Where an installed file is produced by a generator that stamps its version, the installer SHALL
compare that stamp against the incoming file. It SHALL refuse to replace a file whose stamp is newer
than the incoming one, and SHALL report the refusal.

#### Scenario: Incoming artifact is older
- **WHEN** the destination carries a newer generator stamp than the file being installed
- **THEN** the installer refuses to replace it and reports the version on each side

#### Scenario: Stamp missing on one side
- **WHEN** either side carries no generator stamp
- **THEN** the installer treats the comparison as unknown and leaves the destination alone

### Requirement: A module's requirements are mandatory, not advisory
Where a module declares that it requires another module, the installer SHALL refuse to install it
unless that requirement is satisfied. A declared requirement SHALL NOT be treated as advisory.

#### Scenario: A required module is absent
- **WHEN** a module requiring another is installed into a project that does not have it
- **THEN** the install fails and names the missing requirement

#### Scenario: Requirements are satisfied
- **WHEN** every declared requirement is present
- **THEN** the install proceeds

### Requirement: A project installs the modules it asked for
The installer SHALL install only the modules a project has asked for, and SHALL NOT install a module
because it is available. A project's set of installed modules SHALL be readable.

#### Scenario: An unrequested module is not installed
- **WHEN** a project asks for one module and others are available
- **THEN** only the requested module's files are installed

#### Scenario: The installed set is readable
- **WHEN** a project's install record is read
- **THEN** it states which modules are installed and at which version
