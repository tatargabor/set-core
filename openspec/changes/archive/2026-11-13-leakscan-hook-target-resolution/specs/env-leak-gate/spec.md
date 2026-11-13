## MODIFIED Requirements

### Requirement: Both actors are bound at commit time
`set-leakscan --install-hooks` SHALL write `pre-commit` and `commit-msg` hook scripts (and refresh `pre-push`) into the repository's hook directory, guarded by an installer marker: it SHALL write a hook only when the file is absent or begins with the installer's own marker, and SHALL refuse to touch a hook it did not write. The agent-side PreToolUse gate SHALL additionally fire on `git commit` — including commands carrying git's two-token option forms such as `-c <key>=<value>` and `-C <path>` — running the staged scan and scanning any `-m` or `-F` message text, so an agent is bound at commit the way it already is at push.

The agent-side gate SHALL scan the directory the command will run in: every `cd` and `pushd` before the publishing verb applied in order, each relative to the one before it, then the verb's own `-C <path>`, with `~` and variables assigned earlier in the same command or set in the environment expanded. A resolution is CERTAIN only when every step could be followed. When a certain resolution lands outside any git repository the gate SHALL NOT refuse — git refuses the command itself — and SHALL say on standard error that it did not scan. An uncertain resolution (an unresolved variable, `cd -`, `popd`, a directory that does not exist yet) SHALL NEVER fail open: the gate falls back to the session directory and refuses when it cannot scan. When the scanner itself crashes, the gate SHALL still refuse, and SHALL say that the scanner crashed rather than report a finding.

#### Scenario: A fresh clone with no hooks
- **WHEN** `--install-hooks` runs in a repository whose hook directory has no `pre-commit`
- **THEN** the hooks SHALL be created and a re-run SHALL report them already in place rather than rewriting

#### Scenario: A hand-written pre-commit hook
- **WHEN** `--install-hooks` runs where `pre-commit` exists without the installer marker
- **THEN** the installer SHALL leave it untouched and say so

#### Scenario: An agent committing a leaking message
- **WHEN** a session runs `git commit -m "..."` whose message text carries an env-marker
- **THEN** the PreToolUse gate SHALL block the command before git runs

#### Scenario: A commit behind a config override is still gated
- **WHEN** a session runs `git -c <key>=<value> commit` whose staged content or message carries an env-marker
- **THEN** the PreToolUse gate SHALL block the command before git runs

#### Scenario: A relative cd chain back to the repository root
- **WHEN** a session in a repository's root runs `cd a/b/c && … && cd ../../.. && git commit`
- **THEN** the gate SHALL scan that repository's staged content, passing a clean commit and refusing a leaking one

#### Scenario: A followed path outside any repository
- **WHEN** every `cd` of the command can be followed and the result is not inside a git repository
- **THEN** the gate SHALL exit 0 and say on standard error that it did not scan

#### Scenario: An unfollowable cd never fails open
- **WHEN** the command's `cd` names an unset variable and the session directory is not a repository
- **THEN** the gate SHALL refuse the command

#### Scenario: A scanner crash is named as a crash
- **WHEN** `set-leakscan` exits with a traceback
- **THEN** the gate SHALL refuse the command and its message SHALL say the scanner crashed, not that content must not enter the history
