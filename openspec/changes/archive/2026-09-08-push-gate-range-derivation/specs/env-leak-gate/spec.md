## MODIFIED Requirements

### Requirement: Outside commit mode, env-marker findings follow the publication policy, measured over what the push publishes
In range (push) mode, env-marker findings SHALL be reported and SHALL block per the existing remote-visibility policy — the same policy as consumer names. In tree mode the category SHALL NOT run at all. The range SHALL be derived from the refs the push actually publishes (the pre-push hook's stdin), never from the branch's upstream configuration alone: each pushed ref SHALL contribute its remote-side SHA as the range base; a ref whose remote side does not exist yet SHALL be scanned from the merge-base with the nearest remote-tracking ref; a push that only deletes refs SHALL be treated as publishing nothing. A range that cannot resolve SHALL refuse the scan as unrun (exit 2) — never report a clean zero. When no base is derivable at all, the whole-tree checks SHALL still run and block as usual, and the env-marker category's blindness SHALL be announced in the report.

#### Scenario: Old contamination does not block a clean push
- **WHEN** a push range contains no added env-marker lines while the wider tree does
- **THEN** the push SHALL NOT be refused by the env-marker category

#### Scenario: The first push of a branch is scanned
- **WHEN** a branch is pushed whose remote-side ref does not exist yet, so no upstream configuration covers the push
- **THEN** the scan SHALL cover the commits unique to the local side, derived from the merge-base with a remote-tracking ref, and SHALL refuse a leaking HEAD

#### Scenario: An unresolvable range refuses blind
- **WHEN** a range names a ref that does not resolve
- **THEN** the scan SHALL exit 2 with a refusal naming the range, and SHALL NOT report a clean result

#### Scenario: A push with no derivable base announces its blindness
- **WHEN** a push has neither an upstream range nor a common history with any remote-tracking ref
- **THEN** the whole-tree checks SHALL still run and block per the publication policy, and the report SHALL state that the env-marker check has no base for this push

### Requirement: Both actors are bound at commit time
`set-leakscan --install-hooks` SHALL write `pre-commit` and `commit-msg` hook scripts (and refresh `pre-push`) into the repository's hook directory, guarded by an installer marker: it SHALL write a hook only when the file is absent or begins with the installer's own marker, and SHALL refuse to touch a hook it did not write. The agent-side PreToolUse gate SHALL additionally fire on `git commit` — including commands carrying git's two-token option forms such as `-c <key>=<value>` and `-C <path>` — running the staged scan and scanning any `-m` or `-F` message text, so an agent is bound at commit the way it already is at push.

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
