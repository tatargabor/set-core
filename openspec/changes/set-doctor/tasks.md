## 1. The doctor

- [x] 1.1 `lib/set_doctor/checks.py`: the `Check` record, status vocabulary, the sections (install, checkout, tools, mcp, projects, bus, providers, github), each check with its fix command
- [x] 1.2 `lib/set_doctor/mcp_probe.py`: stdio MCP probe (initialize + kb_search) against a throwaway repository, with a timeout
- [x] 1.3 `lib/set_doctor/cli.py` + `bin/set-doctor`: text and `--json` (`set-doctor/1`), `--project`, `--offline`, `--deep`, `--live`, `--strict`, exit code
- [x] 1.4 `install.sh`: `set-doctor` in the installed commands
- [x] 1.5 `set-kb doctor`: the `linked` check

## 2. Tests

- [x] 2.1 `tests/unit/test_set_doctor.py`: a sandbox machine (empty HOME, temp registry, temp Claude config, a fake link dir), one test per spec scenario (19 tests); the `linked` doctor check in `test_kb_linked.py` (2 tests)
- [x] 2.2 Mutation check on the checks that decide `fail`: missing command, missing path, exit code, behind count, MCP project dir, data-repository skip. Each is caught. The missing-path mutant first survived (the git branch also fails, with other words), so the test now asserts the wording. Restored and compared byte for byte
- [x] 2.3 The kb suite, the doctor tests and `test_second_machine.py`: 296 passed

## 3. Verification and docs

- [x] 3.1 Run on this machine (70 registered projects, about 30 s, exit 1). Found: one installer command not linked since the last merge; 21 registry entries whose path is no longer a git repository (old e2e runs); 6 projects whose MCP registration points at one of their worktrees (registered as B-178); deploy versions 44–66 commits behind; projects not on the bus
- [x] 3.2 Sandbox run: `env -i HOME=<empty> PATH=/usr/bin:/bin`, system python 3.10. It ran, wrote nothing into HOME, and reported the missing links, PATH, uv, claude, openspec, sac and gh. It also showed a node v12 as ok, so a Node ≥ 18 floor was added with a test
- [x] 3.3 `docs/reference/set-doctor.md`
