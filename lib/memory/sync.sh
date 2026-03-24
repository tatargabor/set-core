#!/usr/bin/env bash
# set-memory sync: git-based team memory sharing
# Dependencies: sourced by bin/set-memory after infra setup

sync_resolve_identity() {
    local user machine

    user=$(git config user.name 2>/dev/null || true)
    if [[ -z "$user" ]]; then
        user=$(whoami 2>/dev/null || echo "unknown")
    fi
    user=$(echo "$user" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')

    machine=$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo "unknown")
    machine=$(echo "$machine" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-')

    echo "${user}/${machine}"
}

# Resolve sync working directory: set/.work/memory/ if set/ exists, else storage_path
_sync_work_dir() {
    local storage_path="$1"
    if [[ -d "set/.work" ]]; then
        local work_dir="set/.work/memory"
        mkdir -p "$work_dir"
        # Legacy migration: copy .sync-state from storage_path on first use
        if [[ ! -f "$work_dir/.sync-state" && -f "$storage_path/.sync-state" ]]; then
            cp "$storage_path/.sync-state" "$work_dir/.sync-state"
        fi
        echo "$work_dir"
    else
        echo "$storage_path"
    fi
}

# Read a key from .sync-state JSON
sync_get_state() {
    local storage_path="$1"
    local key="$2"
    local work_dir
    work_dir=$(_sync_work_dir "$storage_path")
    local state_file="$work_dir/.sync-state"

    if [[ -f "$state_file" ]]; then
        jq -r ".[\"$key\"] // empty" "$state_file" 2>/dev/null || true
    fi
}

# Update keys in .sync-state JSON (key=value pairs)
sync_update_state() {
    local storage_path="$1"
    shift
    local work_dir
    work_dir=$(_sync_work_dir "$storage_path")
    local state_file="$work_dir/.sync-state"

    local current='{}'
    if [[ -f "$state_file" ]]; then
        current=$(cat "$state_file")
    fi

    while [[ $# -gt 0 ]]; do
        local kv="$1"
        local key="${kv%%=*}"
        local val="${kv#*=}"
        current=$(echo "$current" | jq --arg k "$key" --arg v "$val" '. + {($k): $v}')
        shift
    done

    echo "$current" > "$state_file"
}

# Check sync preconditions. Returns 0 if ready, 1 if should skip, 2 if error.
sync_check_preconditions() {
    # Check shodh-memory
    if [[ -z "$SHODH_PYTHON" ]]; then
        return 1  # silent skip
    fi

    # Check git repo
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        echo "Error: not a git repository" >&2
        return 2
    fi

    # Check remote
    if ! git remote get-url origin >/dev/null 2>&1; then
        echo "Error: no git remote 'origin' found" >&2
        return 2
    fi

    return 0
}

# Push memory to git remote
cmd_sync_push() {
    local rc=0
    sync_check_preconditions || rc=$?
    if [[ $rc -eq 1 ]]; then return 0; fi
    if [[ $rc -eq 2 ]]; then return 1; fi

    local storage_path
    storage_path=$(get_storage_path)
    mkdir -p "$storage_path"

    local identity
    identity=$(sync_resolve_identity)

    # Export memory
    local export_json
    export_json=$(cmd_export) || { echo "Error: export failed" >&2; return 1; }

    # Hash check — skip if nothing changed since last push
    # Normalize: strip volatile fields (exported_at, last_accessed, access_count, importance)
    # so that only content changes trigger a push
    local current_hash
    current_hash=$(echo "$export_json" | jq -S '[.records[] | {id, content, experience_type, tags, metadata}] | sort_by(.id)' | sha256sum | cut -d' ' -f1)
    local last_hash
    last_hash=$(sync_get_state "$storage_path" "last_push_hash")

    if [[ -n "$last_hash" && "$current_hash" == "$last_hash" ]]; then
        echo "Nothing to push."
        return 0
    fi

    local remote_url
    remote_url=$(git remote get-url origin)

    # Get user identity for commits in temp dir
    local git_name git_email
    git_name=$(git config user.name 2>/dev/null || echo "set-memory")
    git_email=$(git config user.email 2>/dev/null || echo "set-memory@localhost")

    local tmpdir
    tmpdir=$(mktemp -d)

    # Check if set-memory branch exists on remote
    local branch_exists=false
    if git ls-remote --heads origin set-memory 2>/dev/null | grep -q set-memory; then
        branch_exists=true
    fi

    if [[ "$branch_exists" == "true" ]]; then
        # Clone existing branch (shallow)
        if ! git clone --branch set-memory --single-branch --depth 1 "$remote_url" "$tmpdir" 2>/dev/null; then
            echo "Error: failed to clone set-memory branch" >&2
            rm -rf "$tmpdir"
            return 1
        fi
    else
        # Create new orphan branch
        git init "$tmpdir" >/dev/null 2>&1
        git -C "$tmpdir" checkout --orphan set-memory 2>/dev/null
        git -C "$tmpdir" remote add origin "$remote_url" 2>/dev/null
    fi

    # Configure git in temp dir
    git -C "$tmpdir" config user.name "$git_name"
    git -C "$tmpdir" config user.email "$git_email"

    # Write export file
    mkdir -p "$tmpdir/$identity"
    echo "$export_json" > "$tmpdir/$identity/memories.json"

    # Stage changes
    git -C "$tmpdir" add -A

    # Check if there are actual changes to commit
    if git -C "$tmpdir" diff --cached --quiet 2>/dev/null; then
        echo "Nothing to push."
        rm -rf "$tmpdir"
        # Update hash even though nothing changed on remote — content matches
        sync_update_state "$storage_path" \
            "last_push_hash=$current_hash" \
            "last_push_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        return 0
    fi

    local timestamp
    timestamp=$(date -Iseconds 2>/dev/null || date)
    git -C "$tmpdir" commit -m "sync: $identity $timestamp" >/dev/null 2>&1

    if git -C "$tmpdir" push origin set-memory 2>/dev/null; then
        sync_update_state "$storage_path" \
            "last_push_hash=$current_hash" \
            "last_push_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "Pushed to $identity"
    else
        echo "Error: push failed (remote may have changed, try again)" >&2
        rm -rf "$tmpdir"
        return 1
    fi

    rm -rf "$tmpdir"
}

# Pull memory from git remote
cmd_sync_pull() {
    local from_filter=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --from) from_filter="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    local rc=0
    sync_check_preconditions || rc=$?
    if [[ $rc -eq 1 ]]; then return 0; fi
    if [[ $rc -eq 2 ]]; then return 1; fi

    local storage_path
    storage_path=$(get_storage_path)
    mkdir -p "$storage_path"

    local identity
    identity=$(sync_resolve_identity)

    # Fetch the set-memory branch
    if ! git fetch origin set-memory 2>/dev/null; then
        echo "No sync branch found. Run 'set-memory sync push' first."
        return 0
    fi

    # Check if remote changed since last pull
    local remote_commit
    remote_commit=$(git rev-parse FETCH_HEAD 2>/dev/null)
    local last_commit
    last_commit=$(sync_get_state "$storage_path" "last_pull_commit")

    if [[ -n "$last_commit" && "$remote_commit" == "$last_commit" && -z "$from_filter" ]]; then
        echo "Up to date."
        return 0
    fi

    # List all memory files on the branch
    local files
    files=$(git ls-tree -r --name-only FETCH_HEAD 2>/dev/null | grep '/memories\.json$' || true)

    if [[ -z "$files" ]]; then
        echo "No memory files found on sync branch."
        sync_update_state "$storage_path" \
            "last_pull_commit=$remote_commit" \
            "last_pull_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        return 0
    fi

    local tmpdir
    tmpdir=$(mktemp -d)

    local total_imported=0
    local total_skipped=0
    local sources_processed=0

    while IFS= read -r file_path; do
        # Extract identity from path: <user>/<machine>/memories.json
        local source_identity
        source_identity=$(dirname "$file_path")

        # Skip own files
        if [[ "$source_identity" == "$identity" ]]; then
            continue
        fi

        # Apply --from filter
        if [[ -n "$from_filter" && "$source_identity" != "$from_filter" ]]; then
            continue
        fi

        # Extract file content via git show
        local tmp_file="$tmpdir/$(echo "$source_identity" | tr '/' '-').json"
        if ! git show "FETCH_HEAD:$file_path" > "$tmp_file" 2>/dev/null; then
            continue
        fi

        # Import using existing cmd_import (captures JSON result)
        local result
        result=$(cmd_import "$tmp_file" 2>/dev/null) || continue

        local imported skipped
        imported=$(echo "$result" | jq -r '.imported // 0' 2>/dev/null) || imported=0
        skipped=$(echo "$result" | jq -r '.skipped // 0' 2>/dev/null) || skipped=0

        echo "$source_identity: $imported new, $skipped skipped"
        total_imported=$((total_imported + imported))
        total_skipped=$((total_skipped + skipped))
        sources_processed=$((sources_processed + 1))
    done <<< "$files"

    rm -rf "$tmpdir"

    if [[ $sources_processed -eq 0 ]]; then
        echo "No other sources found."
    else
        echo "Total: $total_imported new, $total_skipped skipped from $sources_processed source(s)"
    fi

    sync_update_state "$storage_path" \
        "last_pull_commit=$remote_commit" \
        "last_pull_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

# Sync dispatch: push, pull, status, or push+pull
cmd_sync() {
    if [[ $# -gt 0 ]]; then
        case "$1" in
            push)   shift; cmd_sync_push "$@"; return $? ;;
            pull)   shift; cmd_sync_pull "$@"; return $? ;;
            status) shift; cmd_sync_status "$@"; return $? ;;
            -*)
                echo "Error: unknown option '$1'" >&2
                echo "Usage: set-memory sync [push|pull|status]" >&2
                return 1
                ;;
            *)
                echo "Error: unknown sync subcommand '$1'" >&2
                echo "Usage: set-memory sync [push|pull|status]" >&2
                return 1
                ;;
        esac
    fi

    # No subcommand: push + pull
    echo "--- Push ---"
    cmd_sync_push || true
    echo ""
    echo "--- Pull ---"
    cmd_sync_pull
}

# Show sync status
cmd_sync_status() {
    local rc=0
    sync_check_preconditions || rc=$?
    if [[ $rc -eq 1 ]]; then echo "shodh-memory not installed"; return 0; fi
    if [[ $rc -eq 2 ]]; then return 1; fi

    local storage_path
    storage_path=$(get_storage_path)
    local identity
    identity=$(sync_resolve_identity)

    echo "Identity: $identity"
    echo ""

    # Show local state
    local last_push_at last_pull_at
    last_push_at=$(sync_get_state "$storage_path" "last_push_at")
    last_pull_at=$(sync_get_state "$storage_path" "last_pull_at")

    if [[ -n "$last_push_at" || -n "$last_pull_at" ]]; then
        echo "Last sync:"
        [[ -n "$last_push_at" ]] && echo "  Push: $last_push_at"
        [[ -n "$last_pull_at" ]] && echo "  Pull: $last_pull_at"
    else
        echo "Never synced."
    fi
    echo ""

    # Show remote sources
    echo "Remote sources:"
    if git fetch origin set-memory 2>/dev/null; then
        local files
        files=$(git ls-tree -r --name-only FETCH_HEAD 2>/dev/null | grep '/memories\.json$' || true)

        if [[ -n "$files" ]]; then
            while IFS= read -r file_path; do
                local source
                source=$(dirname "$file_path")
                if [[ "$source" == "$identity" ]]; then
                    echo "  $source (you)"
                else
                    echo "  $source"
                fi
            done <<< "$files"
        else
            echo "  (none)"
        fi
    else
        echo "  (no sync branch)"
    fi
}

# ============================================================
# Metrics & Reporting
# ============================================================

