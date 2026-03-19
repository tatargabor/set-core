#!/usr/bin/env bash
# set-memory migrate: schema versioning and data migrations
# Dependencies: sourced by bin/set-memory after infra setup

migrations_read() {
    local storage_path="$1"
    local mig_file="$storage_path/.migrations"
    if [[ -f "$mig_file" ]]; then
        cat "$mig_file"
    else
        echo '{"applied":[]}'
    fi
}

# Write the .migrations state file atomically.
migrations_write() {
    local storage_path="$1"
    local data="$2"
    local mig_file="$storage_path/.migrations"
    local tmp_file="$mig_file.tmp.$$"
    echo "$data" > "$tmp_file"
    mv "$tmp_file" "$mig_file"
}

# Check if a migration ID has been applied.
migration_is_applied() {
    local storage_path="$1"
    local migration_id="$2"
    local state
    state=$(migrations_read "$storage_path")
    echo "$state" | jq -e --arg id "$migration_id" '.applied | index($id) != null' >/dev/null 2>&1
}

# Mark a migration as applied.
migration_mark_applied() {
    local storage_path="$1"
    local migration_id="$2"
    local state
    state=$(migrations_read "$storage_path")
    local new_state
    new_state=$(echo "$state" | jq --arg id "$migration_id" '.applied += [$id] | .last_run = now | .last_run = (now | todate)')
    migrations_write "$storage_path" "$new_state"
}

# Migration 001: Add branch:unknown tag to memories without any branch:* tag
migrate_001_branch_tags() {
    local storage_path="$1"

    if ! cmd_health >/dev/null 2>&1; then
        return 0
    fi

    _SHODH_STORAGE="$storage_path" \
    run_with_lock run_shodh_python -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
memories = m.list_memories()
updated = 0
for mem in memories:
    tags = mem.get('tags', [])
    has_branch = any(t.startswith('branch:') for t in tags)
    if not has_branch:
        new_tags = tags + ['branch:unknown']
        try:
            # shodh-memory has no update_memory — delete and re-create
            m.forget(mem['id'])
            m.remember(
                mem.get('content', ''),
                memory_type=mem.get('experience_type', 'Context'),
                tags=new_tags,
                entities=mem.get('entities', []),
                metadata=mem.get('metadata', {}),
                is_failure=mem.get('is_failure', False),
                is_anomaly=mem.get('is_anomaly', False),
            )
            updated += 1
        except Exception as e:
            print(f'Migration warning: {e}', file=sys.stderr)
print(f'{updated} memories tagged with branch:unknown', file=sys.stderr)
" || true
}

# List of all migrations in order. Format: ID:function_name:description
MIGRATIONS=(
    "001:migrate_001_branch_tags:Add branch:unknown tag to pre-existing memories"
)

# Run all pending migrations.
# Returns 0 on success, outputs progress to stderr.
run_migrations() {
    local storage_path="$1"
    local verbose="${2:-false}"
    mkdir -p "$storage_path"

    local count=0
    for entry in "${MIGRATIONS[@]}"; do
        local id func desc
        id="${entry%%:*}"
        local rest="${entry#*:}"
        func="${rest%%:*}"
        desc="${rest#*:}"

        if migration_is_applied "$storage_path" "$id"; then
            [[ "$verbose" == "true" ]] && echo "$id: $desc — already applied"
            continue
        fi

        [[ "$verbose" == "true" ]] && echo -n "$id: $desc — "
        "$func" "$storage_path"
        migration_mark_applied "$storage_path" "$id"
        [[ "$verbose" == "true" ]] && echo "applied"
        count=$((count + 1))
    done

    if [[ $count -gt 0 ]]; then
        echo "Migrating memory storage... done ($count migration(s) applied)" >&2
    fi
}

# Auto-migrate: run pending migrations before storage access.
# Skipped if --no-migrate is in the global args or storage doesn't exist yet.
AUTO_MIGRATE_DONE="${AUTO_MIGRATE_DONE:-false}"
NO_MIGRATE="${NO_MIGRATE:-false}"

auto_migrate() {
    if [[ "$AUTO_MIGRATE_DONE" == "true" ]] || [[ "$NO_MIGRATE" == "true" ]]; then
        return 0
    fi
    AUTO_MIGRATE_DONE=true

    if [[ -z "$SHODH_PYTHON" ]]; then
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)

    # Only run if storage directory exists (don't create it just for migration)
    if [[ ! -d "$storage_path" ]]; then
        return 0
    fi

    run_migrations "$storage_path" false
}

# Manual migrate subcommand
# Usage: set-memory migrate [--status]
cmd_migrate() {
    local show_status=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --status) show_status=true; shift ;;
            *) shift ;;
        esac
    done

    if [[ -z "$SHODH_PYTHON" ]]; then
        return 0
    fi

    local storage_path
    storage_path=$(get_storage_path)
    mkdir -p "$storage_path"

    if [[ "$show_status" == "true" ]]; then
        local state
        state=$(migrations_read "$storage_path")
        local applied
        applied=$(echo "$state" | jq -r '.applied[]' 2>/dev/null || true)

        for entry in "${MIGRATIONS[@]}"; do
            local id func desc
            id="${entry%%:*}"
            local rest="${entry#*:}"
            func="${rest%%:*}"
            desc="${rest#*:}"

            if echo "$applied" | grep -q "^${id}$"; then
                local ts
                ts=$(echo "$state" | jq -r '.last_run // "unknown"' 2>/dev/null)
                echo "$id: $desc — applied ($ts)"
            else
                echo "$id: $desc — pending"
            fi
        done
        return 0
    fi

    # Run all pending migrations (verbose)
    local count=0
    for entry in "${MIGRATIONS[@]}"; do
        local id func desc
        id="${entry%%:*}"
        local rest="${entry#*:}"
        func="${rest%%:*}"
        desc="${rest#*:}"

        if migration_is_applied "$storage_path" "$id"; then
            echo "$id: $desc — already applied"
            continue
        fi

        echo -n "$id: $desc — "
        "$func" "$storage_path"
        migration_mark_applied "$storage_path" "$id"
        echo "applied"
        count=$((count + 1))
    done

    if [[ $count -eq 0 ]]; then
        echo "All migrations applied."
    fi
}

# --- Sync: Git-based memory sharing via orphan branch ---

# Resolve sync identity: <user>/<machine>
# User from git config user.name (lowercase, sanitized), fallback: whoami
# Machine from hostname -s (lowercase, sanitized)
