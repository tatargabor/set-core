#!/usr/bin/env bash
# set-memory core operations: health, remember, recall, proactive, list, forget, context, brain, get, export, import
# Dependencies: sourced by bin/set-memory after infra setup
# Available: SHODH_PYTHON, PROJECT, SHODH_STORAGE, run_with_lock, run_shodh_python, resolve_project, get_storage_path, get_current_branch, get_log_path, auto_migrate

cmd_health() {
    local index_check=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --index) index_check=true; shift ;;
            *) shift ;;
        esac
    done

    if [[ -z "$SHODH_PYTHON" ]]; then
        if [[ "$index_check" == "true" ]]; then
            echo "{}"
        fi
        return 1
    fi

    # Warn about known-broken versions
    local shodh_ver
    shodh_ver=$("$SHODH_PYTHON" -c "import sys; sys._shodh_star_shown = True; from shodh_memory import __version__; print(__version__)" 2>/dev/null) || true
    if [[ "$shodh_ver" == "0.1.80" ]]; then
        echo "Warning: shodh-memory 0.1.80 has a broken native module." >&2
        echo "Downgrade: pip install 'shodh-memory>=0.1.75,!=0.1.80'" >&2
        if [[ "$index_check" == "true" ]]; then
            echo "{}"
        fi
        return 1
    fi

    if [[ "$index_check" == "true" ]]; then
        local storage_path
        storage_path=$(get_storage_path)
        _SHODH_STORAGE="$storage_path" \
        run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
result = {}
try:
    result['index_health'] = m.index_health()
except AttributeError:
    result['index_health'] = {'error': 'index_health not available in this shodh-memory version'}
try:
    result['verify'] = m.verify_index()
except AttributeError:
    pass
print(json.dumps(result, default=str))
" || echo "{}"
    else
        echo "ok"
    fi
    return 0
}

# Save a memory: reads content from stdin
# Usage: echo "content" | set-memory remember --type Decision --tags repo,change
cmd_remember() {
    local memory_type=""
    local tags=""
    local metadata=""
    local is_failure=false
    local is_anomaly=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type) memory_type="$2"; shift 2 ;;
            --tags) tags="$2"; shift 2 ;;
            --metadata) metadata="$2"; shift 2 ;;
            --failure) is_failure=true; shift ;;
            --anomaly) is_anomaly=true; shift ;;
            *) shift ;;
        esac
    done

    if [[ -z "$memory_type" ]]; then
        echo "Error: --type is required" >&2
        return 1
    fi

    # Validate --metadata is valid JSON dict if provided
    if [[ -n "$metadata" ]]; then
        if ! echo "$metadata" | "$SHODH_PYTHON" -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d,dict)" 2>/dev/null; then
            echo "Error: --metadata must be a valid JSON object (e.g., '{\"key\":\"value\"}')" >&2
            return 1
        fi
    fi

    # Map unsupported types to valid shodh-memory types
    case "$memory_type" in
        Observation|observation)
            echo "Note: type '$memory_type' mapped to 'Learning'" >&2
            memory_type="Learning"
            ;;
        Event|event)
            echo "Note: type '$memory_type' mapped to 'Context'" >&2
            memory_type="Context"
            ;;
    esac

    # Read content from stdin
    local content
    content=$(cat)

    if [[ -z "$content" ]]; then
        return 0
    fi

    # Health check — silent no-op if not installed
    if ! cmd_health >/dev/null 2>&1; then
        return 0
    fi

    auto_migrate

    local storage_path
    storage_path=$(get_storage_path)
    mkdir -p "$storage_path"

    # Auto-tag with current branch
    local branch
    branch=$(get_current_branch)
    if [[ -n "$branch" ]]; then
        # Only add if no branch:* tag already present
        if ! echo ",$tags," | grep -q ",branch:"; then
            if [[ -n "$tags" ]]; then
                tags="${tags},branch:${branch}"
            else
                tags="branch:${branch}"
            fi
        fi
    fi

    # Build tags as Python list
    local tags_py="[]"
    if [[ -n "$tags" ]]; then
        tags_py=$(echo "$tags" | tr ',' '\n' | jq -R . | jq -s .)
    fi

    # Pass data via env vars to avoid shell escaping issues
    local rc=0
    _SHODH_STORAGE="$storage_path" \
    _SHODH_CONTENT="$content" \
    _SHODH_TYPE="$memory_type" \
    _SHODH_TAGS="$tags_py" \
    _SHODH_METADATA="${metadata:-"{}"}" \
    _SHODH_IS_FAILURE="$is_failure" \
    _SHODH_IS_ANOMALY="$is_anomaly" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
tags = json.loads(os.environ['_SHODH_TAGS'])
metadata_raw = json.loads(os.environ.get('_SHODH_METADATA', '{}'))
metadata = {str(k): str(v) for k, v in metadata_raw.items()} if metadata_raw else None
is_failure = os.environ.get('_SHODH_IS_FAILURE', 'false') == 'true'
is_anomaly = os.environ.get('_SHODH_IS_ANOMALY', 'false') == 'true'
content = os.environ['_SHODH_CONTENT'].encode('utf-8', errors='replace').decode('utf-8')
m.remember(content, memory_type=os.environ['_SHODH_TYPE'], tags=tags,
    metadata=metadata, is_failure=is_failure, is_anomaly=is_anomaly)
" || rc=$?

    if [[ $rc -ne 0 ]]; then
        echo "set-memory remember: failed (exit $rc), see $(get_log_path)" >&2
    fi
    return 0
}

# Forget (delete) memories
# Usage: set-memory forget <id>
#        set-memory forget --all --confirm
#        set-memory forget --older-than <days>
#        set-memory forget --tags <t1,t2>
#        set-memory forget --pattern <regex>
cmd_forget() {
    local memory_id=""
    local forget_all=false
    local confirm=false
    local older_than=""
    local tags=""
    local pattern=""
    local since=""
    local until=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --all) forget_all=true; shift ;;
            --confirm) confirm=true; shift ;;
            --older-than) older_than="$2"; shift 2 ;;
            --tags) tags="$2"; shift 2 ;;
            --pattern) pattern="$2"; shift 2 ;;
            --since) since="$2"; shift 2 ;;
            --until) until="$2"; shift 2 ;;
            -*)
                echo "Error: Unknown option '$1'" >&2
                return 1
                ;;
            *)
                if [[ -z "$memory_id" ]]; then
                    memory_id="$1"
                fi
                shift
                ;;
        esac
    done

    # Health check — silent no-op if not installed
    if ! cmd_health >/dev/null 2>&1; then
        return 0
    fi

    auto_migrate

    local storage_path
    storage_path=$(get_storage_path)

    # forget --all --confirm
    if [[ "$forget_all" == "true" ]]; then
        if [[ "$confirm" != "true" ]]; then
            echo "Error: --all requires --confirm to prevent accidental deletion" >&2
            return 1
        fi
        local rc=0
        _SHODH_STORAGE="$storage_path" \
        run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
count = m.forget_all()
print(json.dumps({'deleted_count': count}))
" || rc=$?
        return 0
    fi

    # forget --older-than <days>
    if [[ -n "$older_than" ]]; then
        _SHODH_STORAGE="$storage_path" \
        _SHODH_DAYS="$older_than" \
        run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
count = m.forget_by_age(int(os.environ['_SHODH_DAYS']))
print(json.dumps({'deleted_count': count}))
" || echo '{"deleted_count": 0}'
        return 0
    fi

    # forget --tags <t1,t2>
    if [[ -n "$tags" ]]; then
        local tags_py
        tags_py=$(echo "$tags" | tr ',' '\n' | jq -R . | jq -s .)
        _SHODH_STORAGE="$storage_path" \
        _SHODH_TAGS="$tags_py" \
        run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
tags = json.loads(os.environ['_SHODH_TAGS'])
count = m.forget_by_tags(tags)
print(json.dumps({'deleted_count': count}))
" || echo '{"deleted_count": 0}'
        return 0
    fi

    # forget --pattern <regex>
    if [[ -n "$pattern" ]]; then
        _SHODH_STORAGE="$storage_path" \
        _SHODH_PATTERN="$pattern" \
        run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
count = m.forget_by_pattern(os.environ['_SHODH_PATTERN'])
print(json.dumps({'deleted_count': count}))
" || echo '{"deleted_count": 0}'
        return 0
    fi

    # forget --since/--until (date range delete)
    if [[ -n "$since" || -n "$until" ]]; then
        if [[ "$confirm" != "true" ]]; then
            echo "Error: date-range forget requires --confirm" >&2
            return 1
        fi
        _SHODH_STORAGE="$storage_path" \
        _SHODH_SINCE="$since" \
        _SHODH_UNTIL="$until" \
        run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from datetime import datetime, timezone
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
since = os.environ.get('_SHODH_SINCE', '') or None
until = os.environ.get('_SHODH_UNTIL', '') or None

if not since:
    since = '2000-01-01T00:00:00Z'
if not until:
    until = datetime.now(timezone.utc).isoformat()

if hasattr(m, 'forget_by_date'):
    count = m.forget_by_date(since, until)
    print(json.dumps({'deleted_count': count}))
else:
    print(json.dumps({'error': 'forget_by_date not available in this shodh-memory version'}))
" || echo '{"deleted_count": 0}'
        return 0
    fi

    # forget <id> — single memory delete
    if [[ -n "$memory_id" ]]; then
        _SHODH_STORAGE="$storage_path" \
        _SHODH_ID="$memory_id" \
        run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
result = m.forget(os.environ['_SHODH_ID'])
print(json.dumps({'deleted': bool(result), 'id': os.environ['_SHODH_ID']}))
" || echo "{\"deleted\": false, \"id\": \"$memory_id\"}"
        return 0
    fi

    echo "Error: specify a memory ID, or use --all, --older-than, --tags, --pattern, or --since/--until" >&2
    return 1
}

# Semantic search
# Usage: set-memory recall "query" --limit 5 --mode hybrid --tags t1,t2
cmd_recall() {
    local query=""
    local limit=5
    local mode=""
    local tags=""
    local tags_only=false
    local min_importance=""
    local since=""
    local until=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --limit) limit="$2"; shift 2 ;;
            --mode) mode="$2"; shift 2 ;;
            --tags) tags="$2"; shift 2 ;;
            --tags-only) tags_only=true; shift ;;
            --min-importance) min_importance="$2"; shift 2 ;;
            --since) since="$2"; shift 2 ;;
            --until) until="$2"; shift 2 ;;
            -*)
                shift
                ;;
            *)
                if [[ -z "$query" ]]; then
                    query="$1"
                fi
                shift
                ;;
        esac
    done

    # Date-range recall (recall_by_date)
    if [[ -n "$since" || -n "$until" ]]; then
        if ! cmd_health >/dev/null 2>&1; then
            echo "[]"
            return 0
        fi
        auto_migrate
        local storage_path
        storage_path=$(get_storage_path)

        _SHODH_STORAGE="$storage_path" \
        _SHODH_SINCE="$since" \
        _SHODH_UNTIL="$until" \
        _SHODH_LIMIT="$limit" \
        _SHODH_QUERY="$query" \
        run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from datetime import datetime, timezone
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
since = os.environ.get('_SHODH_SINCE', '') or None
until = os.environ.get('_SHODH_UNTIL', '') or None
limit = int(os.environ['_SHODH_LIMIT'])
query = os.environ.get('_SHODH_QUERY', '')

# Default open ends
if not since:
    since = '2000-01-01T00:00:00Z'
if not until:
    until = datetime.now(timezone.utc).isoformat()

if hasattr(m, 'recall_by_date'):
    results = m.recall_by_date(since, until, limit=limit)
else:
    # Fallback: use regular recall and post-filter
    results = m.recall(query or 'date range', limit=limit * 3)
    from datetime import datetime as dt
    s = dt.fromisoformat(since.replace('Z', '+00:00'))
    u = dt.fromisoformat(until.replace('Z', '+00:00'))
    filtered = []
    for r in results:
        ts = r.get('timestamp', r.get('created_at', ''))
        if ts:
            try:
                t = dt.fromisoformat(str(ts).replace('Z', '+00:00'))
                if s <= t <= u:
                    filtered.append(r)
            except (ValueError, TypeError):
                pass
    results = filtered[:limit]

print(json.dumps(results[:limit], default=str))
" || echo "[]"
        return 0
    fi

    # --tags-only requires --tags
    if [[ "$tags_only" == "true" && -z "$tags" ]]; then
        echo "Error: --tags-only requires --tags" >&2
        return 1
    fi

    if [[ -z "$query" && "$tags_only" == "false" ]]; then
        echo "[]"
        return 0
    fi

    # Health check — return empty array if not installed
    if ! cmd_health >/dev/null 2>&1; then
        echo "[]"
        return 0
    fi

    auto_migrate

    local storage_path
    storage_path=$(get_storage_path)

    # Branch-boosted recall: if no explicit --tags and on a branch,
    # issue two queries (branch-filtered + unfiltered) and merge results.
    local branch=""
    if [[ -z "$tags" ]]; then
        branch=$(get_current_branch)
    fi

    if [[ -n "$branch" ]]; then
        # Double-query: branch-filtered first, then unfiltered
        local branch_limit=$(( (limit + 1) / 2 + 1 ))
        local branch_tags_py
        branch_tags_py=$(echo "branch:$branch" | jq -R . | jq -s .)

        _SHODH_STORAGE="$storage_path" \
        _SHODH_QUERY="$query" \
        _SHODH_LIMIT="$limit" \
        _SHODH_BRANCH_LIMIT="$branch_limit" \
        _SHODH_MODE="$mode" \
        _SHODH_BRANCH_TAGS="$branch_tags_py" \
        _SHODH_MIN_IMPORTANCE="$min_importance" \
        run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
limit = int(os.environ['_SHODH_LIMIT'])
branch_limit = int(os.environ['_SHODH_BRANCH_LIMIT'])
mode = os.environ.get('_SHODH_MODE', '')
branch_tags = json.loads(os.environ['_SHODH_BRANCH_TAGS'])
min_imp = os.environ.get('_SHODH_MIN_IMPORTANCE', '')

kwargs_branch = {'limit': branch_limit, 'tags': branch_tags}
kwargs_all = {'limit': limit}
if mode:
    kwargs_branch['mode'] = mode
    kwargs_all['mode'] = mode

# Query 1: branch-specific
branch_results = m.recall(os.environ['_SHODH_QUERY'], **kwargs_branch)
# Query 2: unfiltered
all_results = m.recall(os.environ['_SHODH_QUERY'], **kwargs_all)

# Merge: branch first, then fill with unfiltered (dedup by id)
seen = set()
merged = []
for r in branch_results:
    rid = r.get('id', '')
    if rid not in seen:
        seen.add(rid)
        merged.append(r)
for r in all_results:
    rid = r.get('id', '')
    if rid not in seen:
        seen.add(rid)
        merged.append(r)

# Post-filter by min importance
if min_imp:
    threshold = float(min_imp)
    merged = [r for r in merged if float(r.get('importance', 0)) >= threshold]

print(json.dumps(merged[:limit], default=str))
" || echo "[]"
    else
        # No branch or explicit tags: single query (current behavior)
        local tags_py="[]"
        if [[ -n "$tags" ]]; then
            tags_py=$(echo "$tags" | tr ',' '\n' | jq -R . | jq -s .)
        fi

        _SHODH_STORAGE="$storage_path" \
        _SHODH_QUERY="$query" \
        _SHODH_LIMIT="$limit" \
        _SHODH_MODE="$mode" \
        _SHODH_TAGS="$tags_py" \
        _SHODH_TAGS_ONLY="$tags_only" \
        _SHODH_MIN_IMPORTANCE="$min_importance" \
        run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
tags = json.loads(os.environ.get('_SHODH_TAGS', '[]'))
tags_only = os.environ.get('_SHODH_TAGS_ONLY', 'false') == 'true'
min_imp = os.environ.get('_SHODH_MIN_IMPORTANCE', '')

if tags_only and tags:
    # Fast tag-based lookup
    if hasattr(m, 'recall_by_tags'):
        results = m.recall_by_tags(tags, limit=int(os.environ['_SHODH_LIMIT']))
    else:
        # Fallback: use recall with tags filter
        results = m.recall('', limit=int(os.environ['_SHODH_LIMIT']), tags=tags)
else:
    kwargs = {'limit': int(os.environ['_SHODH_LIMIT'])}
    mode = os.environ.get('_SHODH_MODE', '')
    if mode:
        kwargs['mode'] = mode
    if tags:
        kwargs['tags'] = tags
    results = m.recall(os.environ['_SHODH_QUERY'], **kwargs)

# Post-filter by min importance
if min_imp:
    threshold = float(min_imp)
    results = [r for r in results if float(r.get('importance', 0)) >= threshold]

print(json.dumps(results, default=str))
" || echo "[]"
    fi

    return 0
}

# Proactive context retrieval — auto-surfaces relevant memories with relevance scores
# Usage: set-memory proactive "conversation context" [--limit N]
cmd_proactive() {
    local context=""
    local limit=5

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --limit) limit="$2"; shift 2 ;;
            -*)
                shift
                ;;
            *)
                if [[ -z "$context" ]]; then
                    context="$1"
                fi
                shift
                ;;
        esac
    done

    if [[ -z "$context" ]]; then
        echo "[]"
        return 0
    fi

    # Health check — return empty array if not installed
    if ! cmd_health >/dev/null 2>&1; then
        echo "[]"
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)

    _SHODH_STORAGE="$storage_path" \
    _SHODH_CONTEXT="$context" \
    _SHODH_LIMIT="$limit" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
limit = int(os.environ['_SHODH_LIMIT'])
context = os.environ['_SHODH_CONTEXT']

if hasattr(m, 'proactive_context'):
    raw = m.proactive_context(context, max_results=limit, auto_ingest=False, semantic_threshold=0.3)
    results = raw.get('memories', []) if isinstance(raw, dict) else raw

    # Always augment with hybrid recall to catch keyword matches that semantic misses
    hybrid = m.recall(context, limit=limit, mode='hybrid')
    seen = {r.get('content', '')[:50] for r in results}
    hybrid_new = []
    for h in hybrid:
        key = h.get('content', '')[:50]
        if key not in seen:
            seen.add(key)
            h['relevance_score'] = 0.35
            hybrid_new.append(h)

    # Reserve slots for hybrid-only results (up to 2), trim proactive if needed
    if hybrid_new:
        reserve = min(len(hybrid_new), 2)
        results = results[:max(limit - reserve, 0)] + hybrid_new[:reserve]
    results = results[:limit]
    print(json.dumps(results, default=str))
else:
    # Fallback: use recall with hybrid mode (old shodh-memory without proactive_context)
    results = m.recall(context, limit=limit, mode='hybrid')
    for r in results:
        r['relevance_score'] = 'N/A'
    print(json.dumps(results, default=str))
" || echo "[]"

    return 0
}

# List all memories for current project
# Usage: set-memory list [--type Decision] [--limit 20]
cmd_list() {
    local memory_type=""
    local limit=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type) memory_type="$2"; shift 2 ;;
            --limit) limit="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    # Health check — return empty array if not installed
    if ! cmd_health >/dev/null 2>&1; then
        echo "[]"
        return 0
    fi

    auto_migrate

    local storage_path
    storage_path=$(get_storage_path)

    # If storage dir doesn't exist yet, no memories
    if [[ ! -d "$storage_path" ]]; then
        echo "[]"
        return 0
    fi

    _SHODH_STORAGE="$storage_path" \
    _SHODH_TYPE="$memory_type" \
    _SHODH_LIMIT="$limit" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
kwargs = {}
mt = os.environ.get('_SHODH_TYPE', '')
if mt:
    kwargs['memory_type'] = mt
lim = os.environ.get('_SHODH_LIMIT', '')
if lim:
    kwargs['limit'] = int(lim)
memories = m.list_memories(**kwargs)
print(json.dumps(memories, default=str))
" || echo "[]"

    return 0
}

# Context summary by category
# Usage: set-memory context [topic]
cmd_context() {
    local topic=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -*) shift ;;
            *)
                if [[ -z "$topic" ]]; then
                    topic="$1"
                fi
                shift
                ;;
        esac
    done

    if ! cmd_health >/dev/null 2>&1; then
        echo "{}"
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)

    _SHODH_STORAGE="$storage_path" \
    _SHODH_TOPIC="$topic" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
topic = os.environ.get('_SHODH_TOPIC', '')
try:
    if topic:
        result = m.context_summary(max_items=5, include_decisions=True, include_learnings=True, include_context=True)
    else:
        result = m.context_summary(max_items=5, include_decisions=True, include_learnings=True, include_context=True)
    print(json.dumps(result, default=str))
except AttributeError:
    print(json.dumps({'error': 'context_summary not available in this shodh-memory version'}))
" || echo "{}"

    return 0
}

# 3-tier memory visualization
# Usage: set-memory brain
cmd_brain() {
    if ! cmd_health >/dev/null 2>&1; then
        echo "{}"
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)

    _SHODH_STORAGE="$storage_path" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
try:
    result = m.brain_state(longterm_limit=100)
    print(json.dumps(result, default=str))
except AttributeError:
    print(json.dumps({'error': 'brain_state not available in this shodh-memory version'}))
" || echo "{}"

    return 0
}

# Memory quality diagnostics
# Usage: set-memory stats [--json]

cmd_export() {
    local output_file=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --output) output_file="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    # Health check — silent no-op if not installed
    if ! cmd_health >/dev/null 2>&1; then
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)
    local project
    project=$(resolve_project)

    local json_output
    json_output=$(_SHODH_STORAGE="$storage_path" \
    _SHODH_PROJECT="$project" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from datetime import datetime, timezone
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
records = m.list_memories()
export_data = {
    'version': 1,
    'format': 'set-memory-export',
    'project': os.environ['_SHODH_PROJECT'],
    'exported_at': datetime.now(timezone.utc).isoformat(),
    'count': len(records),
    'records': records
}
print(json.dumps(export_data, indent=2, default=str))
") || { echo '{"version":1,"format":"set-memory-export","count":0,"records":[]}'; return 0; }

    if [[ -n "$output_file" ]]; then
        echo "$json_output" > "$output_file"
    else
        echo "$json_output"
    fi
    return 0
}

# Import memories from JSON export file
# Usage: set-memory import FILE [--dry-run]
cmd_import() {
    local import_file=""
    local dry_run=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run) dry_run=true; shift ;;
            -*)
                echo "Error: Unknown option '$1'" >&2
                return 1
                ;;
            *)
                if [[ -z "$import_file" ]]; then
                    import_file="$1"
                fi
                shift
                ;;
        esac
    done

    if [[ -z "$import_file" ]]; then
        echo "Error: import file path required" >&2
        return 1
    fi

    if [[ ! -f "$import_file" ]]; then
        echo "Error: file not found: $import_file" >&2
        return 1
    fi

    # Health check — silent no-op if not installed
    if ! cmd_health >/dev/null 2>&1; then
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)
    mkdir -p "$storage_path"

    _SHODH_STORAGE="$storage_path" \
    _SHODH_FILE="$import_file" \
    _SHODH_DRY_RUN="$dry_run" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory

# Read and validate import file
file_path = os.environ['_SHODH_FILE']
dry_run = os.environ.get('_SHODH_DRY_RUN', 'false') == 'true'

try:
    with open(file_path, 'r') as f:
        data = json.load(f)
except json.JSONDecodeError as e:
    print(json.dumps({'error': f'Invalid JSON: {e}'}))
    sys.exit(1)

# Validate format
if data.get('format') != 'set-memory-export':
    print(json.dumps({'error': 'Invalid file: missing or wrong format field (expected set-memory-export)'}))
    sys.exit(1)

if data.get('version', 0) != 1:
    print(json.dumps({'error': f\"Unsupported version: {data.get('version')} (only version 1 supported)\"}))
    sys.exit(1)

records = data.get('records', [])

# Open memory store and build known-ID set for dedup
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
existing = m.list_memories()

known_ids = set()
for rec in existing:
    known_ids.add(rec['id'])
    orig = rec.get('metadata', {}).get('original_id')
    if orig:
        known_ids.add(orig)

imported = 0
skipped = 0
errors = 0

for rec in records:
    # Check all dedup conditions
    rec_id = rec.get('id', '')
    rec_original_id = rec.get('metadata', {}).get('original_id', '')

    if rec_id in known_ids:
        skipped += 1
        continue
    if rec_original_id and rec_original_id in known_ids:
        skipped += 1
        continue

    if dry_run:
        imported += 1
        continue

    try:
        # Build metadata with original_id tracking
        metadata = dict(rec.get('metadata', {}) or {})
        metadata['original_id'] = rec_id

        m.remember(
            rec.get('content', ''),
            memory_type=rec.get('experience_type', 'Context'),
            tags=rec.get('tags', []),
            entities=rec.get('entities', []),
            metadata=metadata,
            is_failure=rec.get('is_failure', False),
            is_anomaly=rec.get('is_anomaly', False),
        )
        imported += 1
        # Add to known set so subsequent records in same file are deduped
        known_ids.add(rec_id)
    except Exception as e:
        errors += 1

if dry_run:
    print(json.dumps({'would_import': imported, 'would_skip': skipped, 'dry_run': True}))
else:
    print(json.dumps({'imported': imported, 'skipped': skipped, 'errors': errors}))
"
    return $?
}

# Get single memory by ID
# Usage: set-memory get <memory_id>
cmd_get() {
    local memory_id=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -*) shift ;;
            *)
                if [[ -z "$memory_id" ]]; then
                    memory_id="$1"
                fi
                shift
                ;;
        esac
    done

    if [[ -z "$memory_id" ]]; then
        echo "Error: memory ID required" >&2
        return 1
    fi

    if ! cmd_health >/dev/null 2>&1; then
        echo "{}"
        return 0
    fi

    auto_migrate

    local storage_path
    storage_path=$(get_storage_path)

    _SHODH_STORAGE="$storage_path" \
    _SHODH_ID="$memory_id" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
try:
    result = m.get_memory(os.environ['_SHODH_ID'])
    print(json.dumps(result, default=str))
except Exception:
    print('{}')
" || echo "{}"

    return 0
}
