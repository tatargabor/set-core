<!-- The scope blocks sit BEFORE the delta header, not inside it. The delta parser
     ends a section at any `##` heading, so `## IN SCOPE` written after
     `## ADDED Requirements` — which is what the generated instruction asks for —
     truncates the section to zero requirements. -->

## IN SCOPE
- Refusing a shell command that would take, publish or move work another session
  in the same checkout is holding
- Knowing which paths the committing session itself staged, so the refusal fires
  only on the real hazard
- Saying, in the refusal, which paths were found and what to run instead

## OUT OF SCOPE
- What may be published outside the machine — `git push` and `git tag` remain
  `set-leakscan`'s question, and neither guard subsumes the other
- Deciding which agent *should* own a path, or resolving the conflict for them
- Dispatched orchestration agents: each git worktree carries its own index, so
  they are not exposed to this hazard
- Any repair of an incident that already happened

## ADDED Requirements

### Requirement: A commit may not carry another session's staged work
The guard SHALL refuse a `git commit` that names no pathspec while the index holds
a path the committing session did not stage. The refusal SHALL name the foreign
paths and SHALL name the remedy.

#### Scenario: A pathspec-less commit over a foreign staged path is refused
- **WHEN** a session runs `git commit` with no pathspec, and the index holds a path
  that session did not stage
- **THEN** the command is refused, the foreign paths are listed, and the refusal
  names `git commit -- <paths>` as the way to commit only the session's own work

#### Scenario: A session's own work commits without interference
- **WHEN** a session runs `git commit` with no pathspec and every staged path was
  staged by that same session
- **THEN** the command is allowed and the guard says nothing

#### Scenario: A commit that names its paths is allowed regardless
- **WHEN** a session runs `git commit` with an explicit pathspec while another
  session's path is staged
- **THEN** the command is allowed, because that form commits only the named paths
  and leaves the other session's staged entry in the index

#### Scenario: Amending is the same act
- **WHEN** a session runs `git commit --amend` with no pathspec while a foreign path
  is staged
- **THEN** it is refused on the same ground, because amending also publishes the index

### Requirement: A staging command may not sweep what it was not given
The guard SHALL refuse the staging forms that take everything rather than what they
were told: `git add -A`, `git add --all`, `git add .`, and `git add -u` with no
pathspec.

#### Scenario: A sweeping add is refused
- **WHEN** a session runs `git add -A`
- **THEN** the command is refused and the refusal names staging explicit paths instead

#### Scenario: An explicit add is allowed
- **WHEN** a session runs `git add` with one or more explicit paths
- **THEN** the command is allowed

#### Scenario: Staging everything tracked is the same sweep
- **WHEN** a session runs `git commit -a`
- **THEN** it is refused, because it stages every tracked modification in the
  checkout, including modifications another session is holding

### Requirement: Removing another session's work from the working tree is refused
The guard SHALL refuse a pathspec-less `git stash` while the checkout holds work the
running session did not produce.

#### Scenario: A stash that would take another session's files is refused
- **WHEN** a session runs `git stash` with no pathspec, and the checkout holds staged
  or modified paths that session did not stage or modify
- **THEN** the command is refused, and the refusal states that the other session's
  files would be removed from the working tree

#### Scenario: The refusal explains why this one is worse than a commit
- **WHEN** a stash is refused on this ground
- **THEN** the message states that the other session's `git status` would read clean
  and its work would sit in a stash entry it has no reason to look in

### Requirement: Ownership is recorded, and what cannot be attributed is foreign
The guard SHALL record which paths each session stages, keyed by that session, and
SHALL treat a staged path it cannot attribute to the running session as foreign.

#### Scenario: The session's staging is remembered across commands
- **WHEN** a session stages a path and later commits in a separate command
- **THEN** the guard recognises that path as the session's own

#### Scenario: A path staged by nobody the guard saw is foreign
- **WHEN** the index holds a path that no observed command of the running session
  staged
- **THEN** it is treated as foreign, because a path whose owner is unknown is exactly
  the case this guard exists for — an unattributable path SHALL NOT be assumed to be
  the running session's

#### Scenario: A session that staged nothing does not own a populated index
- **WHEN** a session that has staged nothing runs a pathspec-less `git commit` and
  the index is not empty
- **THEN** the command is refused

### Requirement: The guard refuses, and changes nothing itself
The guard SHALL NOT modify the index, the working tree, or any git state. Its only
effects SHALL be to allow the command or to refuse it with an explanation.

#### Scenario: A refusal leaves everything where it was
- **WHEN** the guard refuses a command
- **THEN** the index, the working tree and the stash list are exactly as they were
  before, and the other session's staged entries are untouched

#### Scenario: The guard does not unstage on the session's behalf
- **WHEN** the guard finds a foreign staged path
- **THEN** it does not unstage it, because doing so would take back what another
  session is holding right now

### Requirement: The guard is silent where the hazard does not exist
The guard SHALL NOT refuse a command in a checkout where no other session's work is
present, and SHALL NOT fail a command when it cannot examine the repository.

#### Scenario: A dedicated worktree is not policed
- **WHEN** an agent working in its own git worktree stages its work and commits with
  no pathspec
- **THEN** the command is allowed, because that worktree's index holds only its own
  staged paths

#### Scenario: A command outside a repository passes through
- **WHEN** the command runs somewhere that is not a git repository
- **THEN** the guard allows it rather than erroring

#### Scenario: A non-git command is not inspected
- **WHEN** a session runs a command that is not one of the guarded git verbs
- **THEN** the guard allows it without examining the index
