## ADDED Requirements

### Requirement: A repository can be registered without being deployed into

`set-project register` SHALL add the git repository containing `--path` (default: the current
directory) to the project registry under `--name` (default: the repository directory's name),
with `"deploy": false`. It SHALL write nothing into the repository, and it SHALL NOT change the
default project. On an entry that already has the same name and path, it SHALL set
`deploy: false` and succeed. On a name used by a different path, it SHALL fail without changing
the registry. With `--dry-run` it SHALL change nothing. `set-project init` SHALL refuse a
repository whose registry entry, matched by path, has `deploy: false`, without deploying or
registering anything. install.sh's per-project redeploy SHALL skip such entries.

#### Scenario: Registering a data repository
- **WHEN** `set-project register --path <repo>` runs on a git repository not yet registered
- **THEN** the registry gains `{path, addedAt, deploy: false}` under the directory's name, the default project is unchanged, and `git status --ignored` in the repository is empty

#### Scenario: A hand-made entry is marked
- **WHEN** the registry already holds the same name and path without `deploy`
- **THEN** register sets `deploy: false`, and a second run reports nothing to do

#### Scenario: init refuses it under any name
- **WHEN** `set-project init` (with or without `--name`) runs inside a repository registered with `deploy: false`
- **THEN** it exits 1 naming `set-project remove <name>`, writes nothing into the repository, and adds no registry entry

#### Scenario: The installer skips it
- **WHEN** install.sh lists the registered paths to redeploy
- **THEN** an entry with `deploy: false` is not among them
