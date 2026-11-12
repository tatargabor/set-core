## 1. Config

- [x] 1.1 `lib/set_kb/config.py`: `linked` default `[]`, `LinkedConfig`, validation (project required, no duplicates, scope in `<name>=<value>` form, about a string), outside the corpus-config hash

## 2. Engine

- [x] 2.1 `lib/set_kb/lifecycle.py`: `registry_path` (SET_CORE_REGISTRY → SET_CONFIG_DIR → XDG), `registry_project_root`, `linked_project` (link is the permission, self-link refused), `search_linked` (own config + link scope, one level, every failure an `error`)

## 3. Access

- [x] 3.1 `lib/set_kb/cli.py`: linked blocks on the text page (`NOT SEARCHED` for a failed link, the `get --project` hint), JSON `linked[]` with `project` on every hit, `--no-linked`, `get --project`
- [x] 3.2 `mcp-server/set_mcp_server.py`: `kb_search(linked=True)`, `kb_get(project=None)`

## 4. Tests

- [x] 4.1 `tests/unit/test_kb_linked.py`: linked hit with project and its own path; the link scope applied; one level only; unsearchable link shown and the others still searched; `--no-linked`; the text page; `get --project` and its refusal; self-link refused; config validation; out of the corpus hash; the MCP parameters
- [x] 4.2 Mutation check: the link scope dropped, the link permission removed, the self-link check removed: each makes one test fail. Restored and compared byte for byte
- [x] 4.3 The whole kb suite: `tests/unit/test_kb_*.py` 271 passed (255 before)

## 5. Docs and rollout

- [x] 5.1 `docs/reference/kb-search.md`: the `linked` key and its rules
- [ ] 5.2 Live check: a consumer project links the shared data repository and finds a known page with one search. The consumer adds the link to its own `kb.json`; reported to the requester
