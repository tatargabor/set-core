## MODIFIED Requirements

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

By default the listing SHALL exclude what the project's own ignore rules exclude, and SHALL
include files that exist but are not yet tracked — a file an agent just wrote is exactly the
file a reader wants to open.

Every path in the answer SHALL be the path as the version control system holds it, byte for
byte, and never a rendering of it. *Measured 2026-08-26 on a consumer checkout:* `git ls-files`
renders a name containing a non-ASCII byte as a quoted C-string, so **11 of 1794** paths came
back as `"docs/converted/…\303\263….md"`. Each one produced a directory node named `"docs` that
does not exist, under which the real files sat unreachable: the path the caller sent back named
no file, so opening it was refused. The failure is silent in both directions at once — the tree
gains a folder nobody made, and eleven files that are present look broken rather than missing.

#### Scenario: The listing follows the project's own ignore rules

- **WHEN** a project's files are listed and the project ignores a directory of build output
- **THEN** no file from that directory appears in the listing, and a file that is present in
  the working tree but not yet committed does appear

#### Scenario: A path with a non-ASCII name arrives intact

- **WHEN** a project holds a file whose name contains bytes outside ASCII
- **THEN** the listing carries that name as it is on disk — no surrounding quotes and no
  escape sequences — and the same path, sent back unchanged, opens that file

#### Scenario: A truncated listing SAYS it is truncated

- **WHEN** a project holds more files than the endpoint's cap
- **THEN** the answer carries both the returned entries and the fact that it was cut, with
  the cap and the true count, so no caller can read a short list as a complete one

#### Scenario: A root the screen does not know is refused

- **WHEN** the listing is asked for a root that is not one of the roots the fleet screen is
  built from
- **THEN** the endpoint refuses, and says nothing about what does exist on the machine

## ADDED Requirements

### Requirement: Ignored files can be listed on request

The listing SHALL accept a flag that adds the files the project's own ignore rules exclude,
and SHALL default that flag to OFF so the unasked-for answer is unchanged.

*Why it is asked for rather than assumed:* the ignore rules are the project's own statement
of what is noise, and a listing that overrides them by default buries the source tree. But a
framework directory a project deliberately ignores is exactly what a reader of THIS screen
comes looking for. Measured 2026-08-26 on a consumer checkout: `.set/` is ignored at
`.gitignore:54`, so **0 of its 156 files** were listable, and nothing on the screen said so —
the directory was not empty, not collapsed, and not marked; it was absent.

When the flag is set, the listing SHALL still exclude the heavy build and dependency
directories the non-repository walk already refuses to enter, and the answer SHALL remain
subject to the same cap and the same truncation report. *Measured on the same checkout:*
dropping the ignore rules outright yields **36 149** paths against a cap of 20 000 — a
truncated answer, which would trade one silent absence for another. Excluding those
directories yields **2005**, against 1794 with the flag off.

An entry present only because the flag was set SHALL be distinguishable from one that would
have been listed anyway, so a caller can render the difference rather than merge it.

#### Scenario: The flag is not given

- **WHEN** the listing is requested without the flag
- **THEN** the answer is exactly what the project's ignore rules allow, and no ignored file
  appears

#### Scenario: The flag is given

- **WHEN** the listing is requested with the flag on a project that ignores a framework
  directory
- **THEN** that directory's files appear in the answer, each marked as ignored, while the
  project's build-output and dependency directories still do not

#### Scenario: The flag does not lift the cap

- **WHEN** the flag is given for a project whose ignored files would exceed the cap
- **THEN** the answer is still capped and still reports that it was cut, with the cap and
  the true count

### Requirement: The listing carries each path's version-control status

The listing SHALL carry, for each listed path that is not clean, the status the version
control system reports for it — staged, modified in the working tree, added, deleted,
renamed, untracked, or ignored — so a caller can show which files carry work that is not
committed.

The absence of a path from that map SHALL mean *clean*, and the absence of the map ITSELF
SHALL mean *not known* — a project that is not a repository has no status to report, and a
caller that cannot tell "everything is clean" from "there is nothing to ask" will report
calm it has not verified. The two SHALL therefore be different values in the answer, never
the same empty one.

Reading the status SHALL NOT be allowed to fail the listing: if it cannot be read, the
answer carries the files and no status map, because a list of files with no marks is useful
and an error instead of the list is not.

#### Scenario: A modified and an untracked file are both marked

- **WHEN** a project has one tracked file edited in the working tree and one file that was
  never committed
- **THEN** the listing marks the first as modified and the second as untracked, and marks
  nothing for the files that are unchanged

#### Scenario: A project that is not a repository reports no status

- **WHEN** the listing is asked for a directory that is not a version-controlled project
- **THEN** the answer carries the walked files and NO status map — distinct from a map that
  is present and empty

#### Scenario: Status that cannot be read does not lose the listing

- **WHEN** the status of a project cannot be determined
- **THEN** the listing still answers with its files, and carries no status map
