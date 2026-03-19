## 1. Version Upgrade

- [x] 1.1 Update `pyproject.toml` shodh-memory pin from `>=0.1.75,!=0.1.80` to `>=0.1.81`
- [x] 1.2 Run `pip install -e .` to upgrade to 0.1.81
- [x] 1.3 Verify upgrade: `python3 -c "import shodh_memory; m = shodh_memory.Memory('/tmp/test'); print(m.verify_index())"`

## 2. API Parity — New CLI Subcommands

- [x] 2.1 Add `cmd_verify` to `bin/set-memory` — calls `verify_index()`, prints JSON result
- [x] 2.2 Add `--since`/`--until` flags to `cmd_recall` — calls `recall_by_date(start, end)` when date flags present
- [x] 2.3 Add `--since`/`--until` flags to `cmd_forget` — calls `forget_by_date(start, end)` with `--confirm` required
- [x] 2.4 Add `cmd_consolidation` to `bin/set-memory` — calls `consolidation_report()` or `consolidation_events()` with `--events` flag
- [x] 2.5 Add `cmd_graph_stats` to `bin/set-memory` — calls `graph_stats()`
- [x] 2.6 Add `cmd_flush` to `bin/set-memory` — calls `flush()`
- [x] 2.7 Update main dispatch case statement to route `verify`, `consolidation`, `graph-stats`, `flush`
- [x] 2.8 Update `usage()` text with new commands in appropriate sections
- [x] 2.9 Enhance `cmd_health --index` to include `verify_index()` result when available (hasattr guard)

## 3. Todo System — CLI

- [x] 3.1 Add `cmd_todo` to `bin/set-memory` with subcommand routing (add/list/done/clear)
- [x] 3.2 Implement `todo add` — read stdin, remember with tags `todo,backlog` + metadata `{todo_status: "open"}`, auto-detect active change
- [x] 3.3 Implement `todo list` — recall_by_tags `todo`, filter by metadata `todo_status=open`, format as readable list with ID prefix
- [x] 3.4 Implement `todo list --json` — full JSON output
- [x] 3.5 Implement `todo done <id>` — ID prefix matching, forget by full ID, confirm with content preview
- [x] 3.6 Implement `todo clear --confirm` — forget_by_tags `todo`
- [x] 3.7 Update main dispatch and usage for `todo` subcommand

## 4. Todo System — Slash Command

- [x] 4.1 Create `.claude/commands/wt/todo.md` with routing for add/list/done
- [x] 4.2 Add "do not pursue" instruction to prevent agent from acting on todo content
- [x] 4.3 Register as skill in the skill registry if needed

## 5. MCP Server — New Tools

- [x] 5.1 Add `add_todo(content, tags)` tool to `set-memory-mcp-server.py`
- [x] 5.2 Add `list_todos()` tool to `set-memory-mcp-server.py`
- [x] 5.3 Add `complete_todo(id)` tool to `set-memory-mcp-server.py`
- [x] 5.4 Add `verify_index()` tool to `set-memory-mcp-server.py`
- [x] 5.5 Add `consolidation_report(since)` tool to `set-memory-mcp-server.py`
- [x] 5.6 Add `graph_stats()` tool to `set-memory-mcp-server.py`
- [x] 5.7 Add `recall_by_date(since, until)` tool to `set-memory-mcp-server.py`

## 6. Verification

- [x] 6.1 Test version upgrade: verify `verify_index()` works on real memory store
- [x] 6.2 Test all new CLI subcommands manually (verify, consolidation, graph-stats, flush)
- [x] 6.3 Test todo workflow end-to-end: add → list → done → list (empty)
- [x] 6.4 Test todo slash command in a Claude session
- [x] 6.5 Test MCP server new tools
- [x] 6.6 Test graceful degradation: all new commands with shodh-memory absent
