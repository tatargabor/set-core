# Env Leak Gate Specification

## Purpose

Refuse, at COMMIT time and on both actors (git hooks and the agent-side PreToolUse gate), content that must not enter a repository's history: the machine's own identity, consumer names, credentials — and say loudly what it could not check.

## Requirements

### Requirement: The environment's identity is resolved at run time, never from the repository
`set-leakscan` SHALL derive its env-marker patterns only from the machine at run time: tokens of four or more characters from the local part of `git config user.email` and from `git config user.name`, the local username, and the hostname (full and its first label). It SHALL match ASCII-folded and case-insensitively on word boundaries, SHALL exclude generic tokens carried on a built-in stoplist, and SHALL suppress a token that is part of the repository's own name or remotes. No marker value SHALL be read from, or written to, any file inside a repository.

#### Scenario: A name written with diacritics is still found
- **WHEN** an added line contains the user's name in its accented form
- **THEN** the folded match SHALL report it as an `env-marker` finding

#### Scenario: The public account handle inside a URL is not the prose name
- **WHEN** an added line contains the account handle as one unbroken word inside a `github.com/...` URL
- **THEN** no env-marker finding SHALL be produced, because the handle carries no token boundary — and this SHALL be documented behaviour, not an accident of the regex

#### Scenario: A generic token from the stoplist does not fire
- **WHEN** an added line contains a word carried on the built-in stoplist that also happens to be an identity token
- **THEN** no finding SHALL be produced for that token

### Requirement: A source that cannot be resolved is reported, never silently zero
When an identity source cannot be read (missing git identity, absent hostname), the scan SHALL state that the category is partially blind, in the same direction as its existing registry-skip warning. It SHALL NOT fold the gap into a clean result.

#### Scenario: Git identity is unset
- **WHEN** `git config user.email` and `user.name` are both unset in the scanned repository
- **THEN** the scan SHALL warn that the name-token check is skipped AND still run every check whose sources resolved

### Requirement: The env-marker check measures what a diff adds, never what a file already holds
The env-marker category SHALL be evaluated only against added lines — in staged mode the staged added lines plus the full content of newly added files plus staged file names, in range mode the added lines of the range — and SHALL NOT be applied in tree mode. A file that already carries an env-marker and is modified elsewhere SHALL NOT block on the old lines.

#### Scenario: Pre-existing contamination next to an unrelated edit
- **WHEN** a staged modification touches a file whose unchanged lines contain the user's name
- **THEN** the commit SHALL NOT be refused because of those unchanged lines

#### Scenario: A new line carrying the name
- **WHEN** a staged change adds a line containing the user's name, email, username or hostname
- **THEN** the staged scan SHALL report an `env-marker` finding naming the token class

### Requirement: A staged commit carrying environment-specific content is refused regardless of remote visibility
In staged mode the gate SHALL block on every finding — env-marker included — without consulting remote visibility, because a commit is history and publication is only one of the ways it escapes. Staged mode SHALL skip the tree-wide checks (such as ignored-but-tracked) so that a pre-commit hook stays fast, and its report SHALL point at the local-config layer as the legitimate home for a machine-specific value.

#### Scenario: A hostname in a new file on a private remote
- **WHEN** a new staged file contains the hostname and every remote of the repository is private
- **THEN** the commit SHALL still be refused, with the finding named and the local-config escape described

### Requirement: A commit message carrying environment-specific content is refused before the commit exists
`set-leakscan --message <file>` SHALL scan the text of a commit message against the same checks, and block unconditionally. A `commit-msg` hook SHALL invoke it so that a message carrying the identity, a consumer name, or a credential never becomes a commit.

#### Scenario: A message naming the user
- **WHEN** a commit message contains the user's name
- **THEN** the `commit-msg` hook SHALL exit non-zero and the commit SHALL NOT be created

#### Scenario: A credential pasted into a message
- **WHEN** a commit message contains a credential-shaped string
- **THEN** the `commit-msg` hook SHALL refuse it under the same checks the push gate uses

### Requirement: Both actors are bound at commit time
`set-leakscan --install-hooks` SHALL write `pre-commit` and `commit-msg` hook scripts (and refresh `pre-push`) into the repository's hook directory, guarded by an installer marker: it SHALL write a hook only when the file is absent or begins with the installer's own marker, and SHALL refuse to touch a hook it did not write. The agent-side PreToolUse gate SHALL additionally fire on `git commit`, running the staged scan and scanning any `-m` or `-F` message text, so an agent is bound at commit the way it already is at push.

#### Scenario: A fresh clone with no hooks
- **WHEN** `--install-hooks` runs in a repository whose hook directory has no `pre-commit`
- **THEN** the hooks SHALL be created and a re-run SHALL report them already in place rather than rewriting

#### Scenario: A hand-written pre-commit hook
- **WHEN** `--install-hooks` runs where `pre-commit` exists without the installer marker
- **THEN** the installer SHALL leave it untouched and say so

#### Scenario: An agent committing a leaking message
- **WHEN** a session runs `git commit -m "..."` whose message text carries an env-marker
- **THEN** the PreToolUse gate SHALL block the command before git runs

### Requirement: Outside commit mode, env-marker findings follow the publication policy
In range (push) mode, env-marker findings SHALL be reported and SHALL block per the existing remote-visibility policy — the same policy as consumer names. In tree mode the category SHALL NOT run at all.

#### Scenario: Old contamination does not block a clean push
- **WHEN** a push range contains no added env-marker lines while the wider tree does
- **THEN** the push SHALL NOT be refused by the env-marker category

### Requirement: Deliberate exceptions are recorded in the allow file, not remembered
A `literal:` entry in the existing allow file SHALL suppress any env-marker finding whose line contains that literal, and the refusal message SHALL name the file. The exception SHALL apply line-locally: other lines keep firing.

#### Scenario: A deliberately published identity string
- **WHEN** the allow file carries a `literal:` entry matching a line that would otherwise fire
- **THEN** that line SHALL not block, and a line without the literal SHALL still block
