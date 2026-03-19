#!/usr/bin/env bash
# set-memory maintenance: stats, cleanup, audit, dedup, verify, consolidation, graph_stats, flush, status, projects
# Dependencies: sourced by bin/set-memory after infra + core setup

cmd_stats() {
    local json_mode=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json) json_mode=true; shift ;;
            *) shift ;;
        esac
    done

    if ! cmd_health >/dev/null 2>&1; then
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)

    _SHODH_STORAGE="$storage_path" \
    _SHODH_JSON="$json_mode" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from collections import Counter
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
json_mode = os.environ.get('_SHODH_JSON', 'false') == 'true'

# Get all memories
memories = m.list_memories()
total = len(memories)

# Type distribution
type_dist = Counter(r.get('experience_type', 'unknown') for r in memories)

# Tag frequency (top 10)
tag_counter = Counter()
for r in memories:
    for t in r.get('tags', []):
        tag_counter[t] += 1
tag_dist = dict(tag_counter.most_common(10))

# Importance histogram (5 buckets)
buckets = {'0.0-0.2': 0, '0.2-0.4': 0, '0.4-0.6': 0, '0.6-0.8': 0, '0.8-1.0': 0}
noise_count = 0
for r in memories:
    imp = float(r.get('importance', 0.5))
    if imp < 0.2: buckets['0.0-0.2'] += 1
    elif imp < 0.4: buckets['0.2-0.4'] += 1
    elif imp < 0.6: buckets['0.4-0.6'] += 1
    elif imp < 0.8: buckets['0.6-0.8'] += 1
    else: buckets['0.8-1.0'] += 1
    if imp < 0.3: noise_count += 1

noise_ratio = round(noise_count / total, 2) if total > 0 else 0

if json_mode:
    print(json.dumps({
        'total': total,
        'type_distribution': dict(type_dist),
        'tag_distribution': tag_dist,
        'importance_histogram': buckets,
        'noise_ratio': noise_ratio
    }, default=str))
else:
    print(f'Total memories: {total}')
    print(f'Noise ratio: {noise_ratio:.0%} (importance < 0.3)')
    print()
    print('Type distribution:')
    for t, c in sorted(type_dist.items(), key=lambda x: -x[1]):
        print(f'  {t}: {c}')
    print()
    print('Top tags:')
    for t, c in tag_counter.most_common(10):
        print(f'  {t}: {c}')
    print()
    print('Importance histogram:')
    for bucket, count in buckets.items():
        bar = '#' * count
        print(f'  {bucket}: {count:3d} {bar}')
" || { [[ "$json_mode" == "true" ]] && echo "{}"; }

    return 0
}

# RocksDB LOG.old cleanup — remove accumulated LOG.old files
# Usage: set-memory cleanup-logs
cmd_cleanup_logs() {
    local storage_path
    storage_path=$(get_storage_path) || return 0

    local total_count=0
    local total_bytes=0

    for subdir in memories memory_index; do
        local dir="$storage_path/$subdir"
        [[ -d "$dir" ]] || continue

        while IFS= read -r -d '' f; do
            local size
            size=$(stat -c%s "$f" 2>/dev/null) || continue
            total_bytes=$((total_bytes + size))
            rm -f "$f"
            total_count=$((total_count + 1))
        done < <(find "$dir" -name "LOG.old.*" -mmin +1440 -print0 2>/dev/null)
    done

    if [[ $total_count -gt 0 ]]; then
        local mb=$((total_bytes / 1048576))
        echo "$total_count LOG.old files cleaned (${mb}MB reclaimed)"
    else
        echo "0 files cleaned"
    fi
}

# Memory cleanup — remove low-value and garbage memories
# Usage: set-memory cleanup [--threshold F] [--min-length N] [--dry-run]
cmd_cleanup() {
    local threshold=0.2
    local min_length=20
    local dry_run=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --threshold) threshold="$2"; shift 2 ;;
            --min-length) min_length="$2"; shift 2 ;;
            --dry-run) dry_run=true; shift ;;
            *) shift ;;
        esac
    done

    if ! cmd_health >/dev/null 2>&1; then
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)

    _SHODH_STORAGE="$storage_path" \
    _SHODH_THRESHOLD="$threshold" \
    _SHODH_MIN_LENGTH="$min_length" \
    _SHODH_DRY_RUN="$dry_run" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
threshold = float(os.environ['_SHODH_THRESHOLD'])
min_length = int(os.environ.get('_SHODH_MIN_LENGTH', '20'))
dry_run = os.environ.get('_SHODH_DRY_RUN', 'false') == 'true'

memories = m.list_memories()

# Phase 1: remove garbage (content too short to be useful)
garbage = [r for r in memories if len(r.get('content', '')) < min_length]

# Phase 2: remove low-importance memories
low_value = [r for r in memories if r not in garbage and float(r.get('importance', 0.5)) < threshold]

if dry_run:
    print(json.dumps({'garbage': len(garbage), 'low_importance': len(low_value),
                       'would_delete': len(garbage) + len(low_value), 'dry_run': True}))
else:
    deleted = 0
    for r in garbage + low_value:
        try:
            m.forget(r['id'])
            deleted += 1
        except Exception:
            pass
    print(json.dumps({'deleted_count': deleted, 'garbage': len(garbage), 'low_importance': len(low_value)}))
" || echo '{"deleted_count": 0}'

    return 0
}

# Shared Python dedup engine — used by both audit and dedup commands.
# Outputs JSON with cluster analysis to stdout.
# Env vars: _SHODH_STORAGE, _SHODH_THRESHOLD, _SHODH_MODE (audit|dedup|interactive),
#           _SHODH_DRY_RUN
_DEDUP_PYTHON='
import sys; sys._shodh_star_shown = True
import json, os
from difflib import SequenceMatcher
from collections import defaultdict
from shodh_memory import Memory

storage = os.environ["_SHODH_STORAGE"]
threshold = float(os.environ.get("_SHODH_THRESHOLD", "0.75"))
mode = os.environ.get("_SHODH_MODE", "audit")
dry_run = os.environ.get("_SHODH_DRY_RUN", "false") == "true"

m = Memory(storage_path=storage)
memories = m.list_memories()

if not memories:
    if mode == "audit":
        print(json.dumps({"total": 0, "clusters": 0, "redundant": 0, "unique": 0, "dedup_ratio": 0.0, "top_clusters": []}))
    else:
        print(json.dumps({"deleted_count": 0, "merged_count": 0}))
    sys.exit(0)

# Union-find
parents = list(range(len(memories)))
def find(x):
    while parents[x] != x:
        parents[x] = parents[parents[x]]
        x = parents[x]
    return x
def union(a, b):
    pa, pb = find(a), find(b)
    if pa != pb:
        parents[pa] = pb

# Pairwise similarity
for i in range(len(memories)):
    for j in range(i + 1, len(memories)):
        ratio = SequenceMatcher(None, memories[i]["content"], memories[j]["content"]).ratio()
        if ratio > threshold:
            union(i, j)

# Build clusters
clusters = defaultdict(list)
for i in range(len(memories)):
    clusters[find(i)].append(i)
dup_clusters = {k: v for k, v in clusters.items() if len(v) > 1}

total = len(memories)
num_clusters = len(dup_clusters)
redundant = sum(len(v) - 1 for v in dup_clusters.values())
unique = total - redundant
dedup_ratio = (redundant / total * 100) if total > 0 else 0.0

# Survivor selection: composite score
def score(mem):
    return (
        mem.get("access_count", 0) * 10
        + float(mem.get("importance", 0.5)) * 5
        + len(mem.get("content", "")) / 100
    )

# Build cluster info sorted by size
sorted_clusters = sorted(dup_clusters.values(), key=lambda v: -len(v))
top_clusters = []
for indices in sorted_clusters[:10]:
    cluster_mems = [memories[i] for i in indices]
    scored = sorted(cluster_mems, key=lambda mem: (-score(mem), mem.get("created_at", "")))
    survivor = scored[0]
    victims = scored[1:]
    top_clusters.append({
        "count": len(cluster_mems),
        "preview": survivor["content"][:120],
        "survivor_id": survivor["id"],
        "ids": [mem["id"] for mem in cluster_mems],
        "victim_ids": [mem["id"] for mem in victims],
        "all_tags": list(set(t for mem in cluster_mems for t in mem.get("tags", []))),
        "survivor_tags": survivor.get("tags", []),
    })

result = {
    "total": total,
    "clusters": num_clusters,
    "redundant": redundant,
    "unique": unique,
    "dedup_ratio": round(dedup_ratio, 1),
    "top_clusters": top_clusters,
}

if mode == "audit":
    print(json.dumps(result, default=str))
    sys.exit(0)

# --- Dedup / Interactive mode ---
if dry_run:
    print(json.dumps({"dry_run": True, "clusters": num_clusters, "would_delete": redundant, "top_clusters": top_clusters}, default=str))
    sys.exit(0)

if mode == "interactive":
    # Interactive: print clusters as numbered items to stderr, read decisions from stdin
    import select
    if not sys.stdin.isatty():
        sys.stderr.write("Warning: stdin is not a TTY, falling back to dry-run\n")
        print(json.dumps({"dry_run": True, "clusters": num_clusters, "would_delete": redundant, "top_clusters": top_clusters}, default=str))
        sys.exit(0)

    deleted_count = 0
    merged_count = 0
    for ci, cluster_info in enumerate(top_clusters):
        cluster_mems = [mem for mem in memories if mem["id"] in cluster_info["ids"]]
        scored = sorted(cluster_mems, key=lambda mem: (-score(mem), mem.get("created_at", "")))
        survivor = scored[0]
        victims = scored[1:]

        sys.stderr.write(f"\n--- Cluster {ci+1}/{len(top_clusters)} ({len(cluster_mems)} entries) ---\n")
        for mi, mem in enumerate(scored):
            marker = " *BEST*" if mem["id"] == survivor["id"] else ""
            mid = mem["id"][:8]
            acc = mem.get("access_count", 0)
            imp = float(mem.get("importance", 0.5))
            preview = mem["content"][:80]
            sys.stderr.write(f"  [{mi+1}] {mid}.. | acc={acc} imp={imp:.2f} | {preview}{marker}\n")
        sys.stderr.write("  [k]eep best / [s]kip / [q]uit: ")
        sys.stderr.flush()

        choice = input().strip().lower()
        if choice == "q":
            break
        elif choice == "s":
            continue
        else:
            # Keep best (default)
            merged_tags = list(set(t for mem in cluster_mems for t in mem.get("tags", [])))
            needs_merge = set(merged_tags) != set(survivor.get("tags", []))

            for v in victims:
                try:
                    m.forget(v["id"])
                    deleted_count += 1
                except Exception:
                    pass

            if needs_merge:
                try:
                    m.forget(survivor["id"])
                    m.remember(
                        content=survivor["content"],
                        memory_type=survivor.get("experience_type", "Learning"),
                        tags=merged_tags,
                        importance=float(survivor.get("importance", 0.5)),
                        metadata=survivor.get("metadata", {}),
                        is_failure=survivor.get("is_failure", False),
                        is_anomaly=survivor.get("is_anomaly", False),
                    )
                    merged_count += 1
                except Exception as e:
                    sys.stderr.write(f"  Warning: tag merge failed: {e}\n")

    print(json.dumps({"deleted_count": deleted_count, "merged_count": merged_count}))
    sys.exit(0)

# --- Execute mode (non-interactive) ---
deleted_count = 0
merged_count = 0
for cluster_info in top_clusters:
    cluster_mems = [mem for mem in memories if mem["id"] in cluster_info["ids"]]
    scored = sorted(cluster_mems, key=lambda mem: (-score(mem), mem.get("created_at", "")))
    survivor = scored[0]
    victims = scored[1:]

    merged_tags = list(set(t for mem in cluster_mems for t in mem.get("tags", [])))
    needs_merge = set(merged_tags) != set(survivor.get("tags", []))

    for v in victims:
        try:
            m.forget(v["id"])
            deleted_count += 1
        except Exception:
            pass

    if needs_merge:
        try:
            m.forget(survivor["id"])
            m.remember(
                content=survivor["content"],
                memory_type=survivor.get("experience_type", "Learning"),
                tags=merged_tags,
                importance=float(survivor.get("importance", 0.5)),
                metadata=survivor.get("metadata", {}),
                is_failure=survivor.get("is_failure", False),
                is_anomaly=survivor.get("is_anomaly", False),
            )
            merged_count += 1
        except Exception:
            pass

print(json.dumps({"deleted_count": deleted_count, "merged_count": merged_count}))
'

# Memory audit — report duplicate clusters and memory health
# Usage: set-memory audit [--threshold F] [--json]
cmd_audit() {
    local threshold=0.75
    local json_mode=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --threshold) threshold="$2"; shift 2 ;;
            --json) json_mode=true; shift ;;
            *) shift ;;
        esac
    done

    if ! cmd_health >/dev/null 2>&1; then
        if [[ "$json_mode" == "true" ]]; then
            echo '{"total": 0, "clusters": 0, "redundant": 0, "unique": 0, "dedup_ratio": 0.0, "top_clusters": []}'
        else
            echo "No memories to audit (shodh-memory not available)."
        fi
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)

    if [[ ! -d "$storage_path" ]]; then
        if [[ "$json_mode" == "true" ]]; then
            echo '{"total": 0, "clusters": 0, "redundant": 0, "unique": 0, "dedup_ratio": 0.0, "top_clusters": []}'
        else
            echo "No memories to audit (empty store)."
        fi
        return 0
    fi

    local raw_json
    raw_json=$(_SHODH_STORAGE="$storage_path" \
        _SHODH_THRESHOLD="$threshold" \
        _SHODH_MODE="audit" \
        run_with_lock run_shodh_python -c "$_DEDUP_PYTHON") || {
        [[ "$json_mode" == "true" ]] && echo '{"total": 0, "clusters": 0, "redundant": 0, "unique": 0, "dedup_ratio": 0.0, "top_clusters": []}'
        return 0
    }

    if [[ "$json_mode" == "true" ]]; then
        echo "$raw_json"
    else
        # Human-readable report
        echo "$raw_json" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('Memory Audit Report')
print('=' * 40)
print(f'Total memories:    {d[\"total\"]}')
print(f'Duplicate clusters: {d[\"clusters\"]}')
print(f'Redundant entries:  {d[\"redundant\"]}')
print(f'Unique (estimated): {d[\"unique\"]}')
print(f'Dedup ratio:        {d[\"dedup_ratio\"]}%')
if d['top_clusters']:
    print()
    print('Top duplicate clusters:')
    for c in d['top_clusters']:
        print(f'  [{c[\"count\"]}x] {c[\"preview\"]}')
else:
    print()
    print('No duplicates found.')
if d['redundant'] > 0:
    print()
    print('Run \`set-memory dedup --dry-run\` to preview cleanup.')
"
    fi

    return 0
}

# Memory dedup — remove duplicate memories
# Usage: set-memory dedup [--threshold F] [--dry-run] [--interactive]
cmd_dedup() {
    local threshold=0.75
    local dry_run=false
    local interactive=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --threshold) threshold="$2"; shift 2 ;;
            --dry-run) dry_run=true; shift ;;
            --interactive|-i) interactive=true; shift ;;
            *) shift ;;
        esac
    done

    if ! cmd_health >/dev/null 2>&1; then
        echo '{"deleted_count": 0, "merged_count": 0}'
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)

    if [[ ! -d "$storage_path" ]]; then
        echo '{"deleted_count": 0, "merged_count": 0}'
        return 0
    fi

    local mode="dedup"
    if [[ "$interactive" == "true" ]]; then
        mode="interactive"
    fi

    local shodh_dry_run="false"
    if [[ "$dry_run" == "true" ]]; then
        shodh_dry_run="true"
    fi

    _SHODH_STORAGE="$storage_path" \
    _SHODH_THRESHOLD="$threshold" \
    _SHODH_MODE="$mode" \
    _SHODH_DRY_RUN="$shodh_dry_run" \
    run_with_lock run_shodh_python -c "$_DEDUP_PYTHON" || echo '{"deleted_count": 0, "merged_count": 0}'

    return 0
}

cmd_verify() {
    if ! cmd_health >/dev/null 2>&1; then
        echo "{}"
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)
    mkdir -p "$storage_path"

    _SHODH_STORAGE="$storage_path" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
try:
    result = m.verify_index()
    print(json.dumps(result, default=str))
    if not result.get('is_healthy', True):
        import sys as _sys
        print('Hint: run \"set-memory repair\" to fix orphaned memories', file=_sys.stderr)
except AttributeError:
    print(json.dumps({'error': 'verify_index not available — upgrade shodh-memory to >=0.1.81'}))
" || echo "{}"

    return 0
}

# Repair index integrity — re-index orphaned memories
# Usage: set-memory repair
cmd_repair() {
    if ! cmd_health >/dev/null 2>&1; then
        echo '{"repaired": false, "error": "shodh-memory not available"}'
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)
    mkdir -p "$storage_path"

    _SHODH_STORAGE="$storage_path" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
try:
    result = m.repair_index()
    print(json.dumps(result, default=str))
except AttributeError:
    print(json.dumps({'error': 'repair_index not available — upgrade shodh-memory to >=0.1.81'}))
" || echo '{"repaired": false}'

    return 0
}

# Show consolidation report — memory strengthening/decay events
# Usage: set-memory consolidation [--since ISO] [--events]
cmd_consolidation() {
    if ! cmd_health >/dev/null 2>&1; then
        echo "{}"
        return 0
    fi

    local since=""
    local events_only=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --since) since="$2"; shift 2 ;;
            --events) events_only=true; shift ;;
            *) shift ;;
        esac
    done

    local storage_path
    storage_path=$(get_storage_path)

    _SHODH_STORAGE="$storage_path" \
    _SHODH_SINCE="$since" \
    _SHODH_EVENTS="$events_only" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
since = os.environ.get('_SHODH_SINCE', '') or None
events_only = os.environ.get('_SHODH_EVENTS', 'false') == 'true'
try:
    if events_only:
        result = m.consolidation_events(since=since) if since else m.consolidation_events()
    else:
        if since:
            result = m.consolidation_report(since=since)
        else:
            result = m.consolidation_report()
    print(json.dumps(result, default=str))
except AttributeError:
    print(json.dumps({'error': 'consolidation not available in this shodh-memory version'}))
" || echo "{}"

    return 0
}

# Knowledge graph statistics
# Usage: set-memory graph-stats
cmd_graph_stats() {
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
    result = m.graph_stats()
    print(json.dumps(result, default=str))
except AttributeError:
    print(json.dumps({'error': 'graph_stats not available in this shodh-memory version'}))
" || echo "{}"

    return 0
}

# Flush pending writes to disk
# Usage: set-memory flush
cmd_flush() {
    if ! cmd_health >/dev/null 2>&1; then
        echo '{"flushed": false}'
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
m.flush()
print(json.dumps({'flushed': True}))
" || echo '{"flushed": false}'

    return 0
}

# Show configuration and health status
cmd_status() {
    local json_mode=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json) json_mode=true; shift ;;
            *) shift ;;
        esac
    done

    local project
    project=$(resolve_project)
    local storage_path
    storage_path=$(get_storage_path)

    if [[ "$json_mode" == "true" ]]; then
        # JSON output for GUI consumption
        if cmd_health >/dev/null 2>&1; then
            local count
            count=$(_SHODH_STORAGE="$storage_path" run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
stats = m.get_stats()
print(stats.get('total_memories', 0))
") || count=0
            [[ "$count" =~ ^[0-9]+$ ]] || count=0
            echo "{\"available\": true, \"project\": \"$project\", \"count\": $count, \"storage_path\": \"$storage_path\"}"
        else
            echo "{\"available\": false, \"project\": \"$project\", \"count\": 0, \"storage_path\": \"$storage_path\"}"
        fi
    else
        # Human-readable output
        echo "Shodh-Memory Configuration:"
        echo "  Project: $project"
        echo "  Storage: $storage_path"
        echo ""

        echo -n "Health: "
        if cmd_health >/dev/null 2>&1; then
            echo "available"
            _SHODH_STORAGE="$storage_path" run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
stats = m.get_stats()
print(f'  Memories: {stats.get(\"total_memories\", \"?\")}')" || true
        else
            echo "not installed"
            echo ""
            echo "Install:"
            echo "  pip install shodh-memory"
        fi
    fi
}

# List all projects with memory counts
cmd_projects() {
    if [[ ! -d "$SHODH_STORAGE" ]]; then
        echo "No memory storage found at $SHODH_STORAGE"
        return 0
    fi

    local has_projects=false

    for dir in "$SHODH_STORAGE"/*/; do
        [[ -d "$dir" ]] || continue
        local proj_name
        proj_name=$(basename "$dir")

        # Skip if it's not a shodh-memory storage (no memories subdir)
        [[ -d "$dir/memories" ]] || [[ -d "$dir/memory_index" ]] || continue

        has_projects=true

        if cmd_health >/dev/null 2>&1; then
            local count
            count=$(_SHODH_STORAGE="$dir" run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
stats = m.get_stats()
print(stats.get('total_memories', 0))
") || count="?"
            echo "  $proj_name: $count memories"
        else
            echo "  $proj_name: (shodh-memory not installed)"
        fi
    done

    # Check for legacy storage (sst files directly in root)
    if ls "$SHODH_STORAGE"/*.sst >/dev/null 2>&1; then
        has_projects=true
        echo "  _legacy: (unmigrated global storage)"
    fi

    if [[ "$has_projects" == "false" ]]; then
        echo "No projects with memories found."
    fi
}

# --- Migrations: versioned memory storage transformations ---

# Read the .migrations state file. Returns JSON or '{"applied":[]}' if missing.
