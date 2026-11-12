## 1. Command

- [x] 1.1 `bin/set-project`: `cmd_register` (--name, --path, --dry-run, --no-deploy accepted), dispatch, usage
- [x] 1.2 `bin/set-project`: init refuses a `deploy: false` repository, matched by path
- [x] 1.3 `install.sh`: `install_projects` skips `deploy: false` entries

## 2. Tests

- [x] 2.1 `tests/unit/test_set_project_register.py`: registers + writes nothing + keeps default; from a subdirectory with a name; idempotent + marks a hand-made entry; name collision; dry run; not a repo; init refuses under any name; the installer's own jq filter skips the entry — 8 passed
- [x] 2.2 Mutation check: without init's refusal and without the installer filter, exactly the two matching tests fail; restored and compared byte for byte

## 3. Live

- [x] 3.1 Mark this machine's hand-made data-repo entry with `set-project register` and confirm `deploy: false`
- [x] 3.2 Test isolation: a deploying `init` also registers through the running dashboard (`SET_MANAGER_URL`), which writes the REAL registry; a mutant run left a pytest repo there. Removed it, and the test env now points `SET_MANAGER_URL` at a closed port
