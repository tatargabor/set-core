## Why

A data repository, such as a shared knowledge corpus several projects search, has to be in the
project registry so cross-project search can resolve it by name. The only command that
registers, `set-project init`, also deploys set-core's rules, skills, hooks and settings into
the repository. So such a repository was added to `projects.json` by hand. Then install.sh's
per-project redeploy, which runs `set-project init` in every registered path, would deploy into
it anyway on the next install.

## What Changes

- New `set-project register [--name N] [--path DIR] [--dry-run]` (`--no-deploy` accepted as a
  spelled-out no-op). It registers the git repository with `"deploy": false` and writes nothing
  into the repository. It never sets the default project. It is idempotent, and on an existing
  entry for the same path it marks it `deploy: false`. It refuses a name used by another path.
- `set-project init` refuses a repository registered with `deploy: false`, matched by path,
  whatever `--name` is passed. The error names the way out: `remove`, then `init`.
- install.sh's `install_projects` skips entries with `deploy: false`.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `project-init-deploy`: a registry entry can be no-deploy, and init and the installer honour it.

## Impact

- `bin/set-project`: `cmd_register`, init's refusal, usage text.
- `install.sh`: the per-project redeploy filter.
- `tests/unit/test_set_project_register.py`.
