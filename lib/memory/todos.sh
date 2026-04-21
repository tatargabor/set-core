#!/usr/bin/env bash
# set-memory todo: lightweight task tracking backed by memory system
# Dependencies: sourced by bin/set-memory after infra setup

cmd_todo() {
    local subcmd="${1:-}"
    shift 2>/dev/null || true

    case "$subcmd" in
        add)  cmd_todo_add "$@" ;;
        list) cmd_todo_list "$@" ;;
        done) cmd_todo_done "$@" ;;
        clear) cmd_todo_clear "$@" ;;
        "")
            echo "Usage: set-memory todo <add|list|done|clear>" >&2
            echo "  add [--tags t1,t2] < text    Save a todo (reads from stdin)" >&2
            echo "  list [--json]                 List open todos" >&2
            echo "  done <id>                     Mark todo as done (deletes it)" >&2
            echo "  clear --confirm               Delete all todos" >&2
            return 1
            ;;
        *)
            echo "Error: Unknown todo subcommand '$subcmd'" >&2
            return 1
            ;;
    esac
}

# todo add — save a todo from stdin
cmd_todo_add() {
    local extra_tags=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --tags) extra_tags="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    # Read content from stdin
    local content=""
    if [[ ! -t 0 ]]; then
        content=$(cat)
    fi

    if [[ -z "$content" ]]; then
        echo "Error: No todo text provided. Pipe content: echo \"text\" | set-memory todo add" >&2
        return 1
    fi

    # Health check
    if ! cmd_health >/dev/null 2>&1; then
        echo "Memory system not available."
        return 0
    fi

    auto_migrate

    # Build tags: always include todo,backlog + optional extras + auto-detect change
    local tags="todo,backlog"
    if [[ -n "$extra_tags" ]]; then
        tags="$tags,$extra_tags"
    fi

    # Auto-detect active OpenSpec change
    local change_name=""
    if command -v openspec >/dev/null 2>&1; then
        change_name=$(openspec list --json 2>/dev/null | jq -r '[.changes[] | select(.status == "in-progress")] | .[0].name // empty' 2>/dev/null) || true
    fi
    if [[ -n "$change_name" ]]; then
        tags="$tags,change:$change_name"
    fi

    local storage_path
    storage_path=$(get_storage_path)
    local branch
    branch=$(get_current_branch)
    if [[ -n "$branch" ]]; then
        tags="$tags,branch:$branch"
    fi

    # Daemon-first: avoids RocksDB LOCK conflict with a running set-memoryd.
    # Falls back to direct Memory() only if the daemon module/socket is unreachable.
    _SHODH_STORAGE="$storage_path" \
    _SHODH_CONTENT="$content" \
    _SHODH_TAGS_CSV="$tags" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import os

content = os.environ['_SHODH_CONTENT']
tags_csv = os.environ['_SHODH_TAGS_CSV']
tags_list = [t.strip() for t in tags_csv.split(',') if t.strip()]

saved = False
try:
    from set_memoryd.client import MemoryClient
    client = MemoryClient.for_project()
    client.remember(
        content=content,
        memory_type='Context',
        tags=tags_csv,
        metadata={'todo_status': 'open'},
    )
    saved = True
except Exception:
    pass

if not saved:
    from shodh_memory import Memory
    m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
    m.remember(
        content,
        memory_type='Context',
        tags=tags_list,
        metadata={'todo_status': 'open'},
    )

print('Todo saved: \"' + content[:80] + '\"')
" || echo "Error: failed to save todo" >&2

    return 0
}

# todo list — show open todos
cmd_todo_list() {
    local json_mode=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json) json_mode=true; shift ;;
            *) shift ;;
        esac
    done

    if ! cmd_health >/dev/null 2>&1; then
        if [[ "$json_mode" == "true" ]]; then
            echo "[]"
        else
            echo "No open todos."
        fi
        return 0
    fi

    auto_migrate

    local storage_path
    storage_path=$(get_storage_path)

    _SHODH_STORAGE="$storage_path" \
    _SHODH_JSON="$json_mode" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os

json_mode = os.environ.get('_SHODH_JSON', 'false') == 'true'

results = None
try:
    from set_memoryd.client import MemoryClient
    client = MemoryClient.for_project()
    # Daemon has no recall_by_tags; fetch bulk via list_memories and filter.
    all_mems = client.list_memories(limit=10000)
    results = [r for r in all_mems if 'todo' in (r.get('tags') or [])]
except Exception:
    results = None

if results is None:
    from shodh_memory import Memory
    m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
    if hasattr(m, 'recall_by_tags'):
        results = m.recall_by_tags(['todo'], limit=100)
    else:
        results = m.recall('todo', limit=100, tags=['todo'])

# Filter to open todos only
todos = []
for r in results:
    meta = r.get('metadata', {}) or {}
    status = meta.get('todo_status', 'open')
    if status == 'open':
        todos.append(r)

if json_mode:
    print(json.dumps(todos, default=str))
else:
    if not todos:
        print('No open todos.')
    else:
        for t in todos:
            tid = t.get('id', '???')[:8]
            content = t.get('content', t.get('description', ''))
            ts = str(t.get('timestamp', t.get('created_at', '')))[:10]
            tags = [tg for tg in t.get('tags', []) if tg not in ('todo', 'backlog')]
            tag_str = ' [' + ', '.join(tags) + ']' if tags else ''
            print(f'  {tid}  {content[:72]}{tag_str}  ({ts})')
        print(f'\n{len(todos)} open todo(s)')
" || {
        if [[ "$json_mode" == "true" ]]; then
            echo "[]"
        else
            echo "No open todos."
        fi
    }

    return 0
}

# todo done — delete a todo by ID (prefix match)
cmd_todo_done() {
    local todo_id="${1:-}"

    if [[ -z "$todo_id" ]]; then
        echo "Error: specify a todo ID (use 'set-memory todo list' to see IDs)" >&2
        return 1
    fi

    if ! cmd_health >/dev/null 2>&1; then
        echo "Memory system not available."
        return 0
    fi

    auto_migrate

    local storage_path
    storage_path=$(get_storage_path)

    _SHODH_STORAGE="$storage_path" \
    _SHODH_ID="$todo_id" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import os

prefix = os.environ['_SHODH_ID']

client = None
results = None
try:
    from set_memoryd.client import MemoryClient
    client = MemoryClient.for_project()
    all_mems = client.list_memories(limit=10000)
    results = [r for r in all_mems if 'todo' in (r.get('tags') or [])]
except Exception:
    client = None
    results = None

m = None
if results is None:
    from shodh_memory import Memory
    m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
    if hasattr(m, 'recall_by_tags'):
        results = m.recall_by_tags(['todo'], limit=200)
    else:
        results = m.recall('todo', limit=200, tags=['todo'])

matches = [r for r in results if r.get('id', '').startswith(prefix)]

if len(matches) == 0:
    print(f'Todo not found: {prefix}', file=sys.stderr)
    sys.exit(1)
elif len(matches) > 1:
    print(f'Ambiguous ID prefix \"{prefix}\" matches {len(matches)} todos. Use a longer prefix.', file=sys.stderr)
    sys.exit(1)

todo = matches[0]
full_id = todo['id']
content = todo.get('content', todo.get('description', ''))

if client is not None:
    client.forget(full_id)
else:
    m.forget(full_id)

print(f'Todo done: \"{content[:80]}\"')
" || { echo "Error: failed to complete todo" >&2; return 1; }

    return 0
}

# todo clear — delete all todos
cmd_todo_clear() {
    local confirm=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --confirm) confirm=true; shift ;;
            *) shift ;;
        esac
    done

    if [[ "$confirm" != "true" ]]; then
        echo "Error: Use --confirm to clear all todos" >&2
        return 1
    fi

    if ! cmd_health >/dev/null 2>&1; then
        echo "Memory system not available."
        return 0
    fi

    auto_migrate

    local storage_path
    storage_path=$(get_storage_path)

    _SHODH_STORAGE="$storage_path" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import os

count = None
try:
    from set_memoryd.client import MemoryClient
    client = MemoryClient.for_project()
    count = client.forget_by_tags('todo')
except Exception:
    count = None

if count is None:
    from shodh_memory import Memory
    m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
    count = m.forget_by_tags(['todo'])

print(f'Cleared {count} todos.')
" || echo "Error: failed to clear todos" >&2

    return 0
}
