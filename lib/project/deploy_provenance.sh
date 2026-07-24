#!/usr/bin/env bash
# Deploy provenance ledger — protects consumer-edited files from `set-project init --force`.
#
# THE PROBLEM. The bash deploy engine (`_deploy_commands`, `_deploy_skills`) copied
# unconditionally: `cp -r "$src"/* "$dst"/`. Every file it owns was overwritten on every
# init, whether or not the consumer had edited it. Measured on a live consumer tree that
# meant 10 openspec SKILL.md files, 10 opsx commands, 8 hand-edited `set-*` rules and a
# customised `code-reviewer.md` agent lost per run — silently, because `cp` reports nothing.
#
# WHY A HASH LEDGER AND NOT "SKIP IF EXISTS". "Skip if the file exists" is safe but it
# FREEZES the consumer: the template moves forward and the project never receives another
# framework fix. Comparing against the template does not work either — it cannot tell
# "the consumer edited this" from "the template advanced since we deployed it", and it
# treats both as untouchable.
#
# The ledger closes exactly that gap. At deploy time we record the sha256 of what we
# WROTE. On the next run:
#
#   dst missing, deleted in git    → SKIP   (the project committed its removal)
#   dst missing                    → deploy (new file)
#   ledger hash == sha256(dst)     → deploy (consumer never touched it; the update lands)
#   ledger hash != sha256(dst)     → SKIP   (the consumer owns it now)
#   no ledger entry, dst exists    → SKIP   (unknown provenance — never guess)
#
# The git rule covers the mirror-image blind spot for ABSENT files: the ledger only
# knows what set-core wrote, so on a first init every deleted file reads as new and
# comes back. Measured on a live consumer: 11 files resurrected, every one of them a
# deletion the project had committed on purpose.
#
# The last rule is what makes adoption safe on projects that predate the ledger: the first
# init after this change writes no hashes it did not verify, so nothing pre-existing is
# clobbered. Those files stay skipped until the consumer resolves them by hand (delete the
# file to accept the framework version, or record it deliberately).
#
# Ledger location: `<project>/set/.deploy-manifest.json`, keyed by project-relative path.
#
# Dependencies: set-common.sh (info/warn/success), python3 (JSON merge). Sourced by deploy.sh.

# Path to the provenance ledger for a project.
_pv_ledger_path() {
    printf '%s/set/.deploy-manifest.json' "$1"
}

# sha256 of a file, portable across Linux (sha256sum) and macOS (shasum).
# Prints the bare hex digest, or nothing if the file is unreadable.
_pv_sha256() {
    local file="$1"
    [[ -f "$file" ]] || return 1
    if command -v sha256sum &>/dev/null; then
        sha256sum "$file" 2>/dev/null | awk '{print $1}'
    elif command -v shasum &>/dev/null; then
        shasum -a 256 "$file" 2>/dev/null | awk '{print $1}'
    else
        return 1
    fi
}

# Collect every path git history records as deleted, relative to the project root.
# Written to $_PV_GITDEL, one path per line. Silent no-op when the project is not a
# git repository or git is missing — the file simply stays empty, which reads as
# "no information" and leaves every previous decision unchanged.
#
# Mirrors lib/set_orch/git_intent.py; keep the two in step.
_pv_load_git_deletions() {
    local project_path="$1" prefix top line
    : > "$_PV_GITDEL"

    if [[ "${SET_DEPLOY_IGNORE_GIT_HISTORY:-}" =~ ^(1|true|yes|TRUE|YES)$ ]]; then
        info "  Git deletion history ignored (SET_DEPLOY_IGNORE_GIT_HISTORY set)"
        return 0
    fi
    command -v git &>/dev/null || return 0

    top="$(git -C "$project_path" rev-parse --show-toplevel 2>/dev/null)" || return 0
    [[ -n "$top" ]] || return 0
    prefix="$(git -C "$project_path" rev-parse --show-prefix 2>/dev/null)" || prefix=""

    # `--format=` leaves nothing but path lines. Rename detection stays on, so a moved
    # file is reported as R and correctly does not count as a deletion of the old path.
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        if [[ -n "$prefix" ]]; then
            [[ "$line" == "$prefix"* ]] || continue
            line="${line#"$prefix"}"
        fi
        [[ -n "$line" ]] && printf '%s\n' "$line"
    done < <(git -C "$project_path" log --diff-filter=D --name-only --format= 2>/dev/null) \
        | sort -u > "$_PV_GITDEL"
}

# Does the project's git history record a deletion of this path?
# Only meaningful for a path that is absent right now.
_pv_deleted_in_history() {
    [[ -s "${_PV_GITDEL:-/nonexistent}" ]] || return 1
    grep -Fxq -- "$1" "$_PV_GITDEL" 2>/dev/null
}

# Begin a deploy session: load the ledger into a lookup file and open a staging file.
# Both are process-scoped temp files; _pv_end flushes staging into the ledger.
#
# Sets: _PV_PROJECT, _PV_KNOWN (tab-separated key<TAB>hash), _PV_STAGED, _PV_SKIPPED
_pv_begin() {
    local project_path="$1"
    _PV_PROJECT="$project_path"
    _PV_KNOWN="$(mktemp -t set-pv-known.XXXXXX)"
    _PV_TOMBS="$(mktemp -t set-pv-tombs.XXXXXX)"
    _PV_STAGED="$(mktemp -t set-pv-staged.XXXXXX)"
    _PV_NEWTOMBS="$(mktemp -t set-pv-newtombs.XXXXXX)"
    _PV_GITDEL="$(mktemp -t set-pv-gitdel.XXXXXX)"
    _PV_SKIPPED=0
    _PV_DEPLOYED=0
    _PV_TOMBSTONED=0

    # One history scan per session, not per file.
    _pv_load_git_deletions "$project_path"

    local ledger
    ledger="$(_pv_ledger_path "$project_path")"
    if [[ -f "$ledger" ]] && command -v python3 &>/dev/null; then
        python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
except (OSError, ValueError):
    sys.exit(0)
if not isinstance(data, dict):
    sys.exit(0)
with open(sys.argv[2], 'w') as out:
    for key, digest in (data.get('files') or {}).items():
        if isinstance(key, str) and isinstance(digest, str):
            out.write(f'{key}\t{digest}\n')
with open(sys.argv[3], 'w') as out:
    for key in (data.get('tombstones') or []):
        if isinstance(key, str):
            out.write(f'{key}\n')
" "$ledger" "$_PV_KNOWN" "$_PV_TOMBS" 2>/dev/null || true
    fi
}

# Is this path recorded as deliberately removed by the project?
_pv_is_tombstoned() {
    [[ -s "${_PV_TOMBS:-/nonexistent}" ]] || return 1
    grep -Fxq -- "$1" "$_PV_TOMBS" 2>/dev/null
}

# Look up the recorded hash for a project-relative key. Prints it, or nothing.
_pv_known_hash() {
    [[ -s "${_PV_KNOWN:-/nonexistent}" ]] || return 1
    awk -F'\t' -v k="$1" '$1 == k { print $2; found=1; exit } END { exit !found }' "$_PV_KNOWN"
}

# Decide whether a destination may be written.
#   $1 project-relative key   $2 destination file
# Returns 0 = deploy, 1 = skip. On skip, prints the reason to stdout.
_pv_should_deploy() {
    local key="$1" dst="$2"

    # Deliberately removed by the project — recreating it would re-arm content the
    # project threw out on purpose. Only an explicit edit of the ledger brings it back.
    if _pv_is_tombstoned "$key"; then
        printf 'removed by the project (tombstoned)'
        return 1
    fi

    local known dst_hash
    known="$(_pv_known_hash "$key" 2>/dev/null)" || known=""

    if [[ ! -e "$dst" ]]; then
        if [[ -n "$known" ]]; then
            # We deployed it once, it is gone now: the project deleted it. Record that
            # as history so the next run decides from fact rather than from chance.
            _pv_tombstone "$key"
            printf 'deleted by the project — recorded as tombstone'
            return 1
        fi
        # Unknown to the ledger. On a first init that covers both a genuinely new file
        # and one the project deleted long before the ledger existed; the project's own
        # git history is the only record that can tell them apart.
        if _pv_deleted_in_history "$key"; then
            _pv_tombstone "$key"
            printf 'deleted in the project'"'"'s git history — recorded as tombstone'
            return 1
        fi
        return 0                            # genuinely new — nothing to lose
    fi

    if [[ -z "$known" ]]; then
        printf 'unknown provenance (predates the ledger) — not overwriting'
        return 1
    fi

    dst_hash="$(_pv_sha256 "$dst")" || {
        printf 'unreadable destination — not overwriting'
        return 1
    }

    if [[ "$dst_hash" == "$known" ]]; then
        return 0                            # untouched since we wrote it
    fi

    printf 'modified by the project since the last deploy'
    return 1
}

# May set-core EDIT this file in place?
#   $1 project-relative key   $2 file
# Returns 0 only when the ledger says we wrote it and it still carries the exact bytes
# we wrote. Anything else — no entry, a changed hash, an unreadable file — belongs to
# the project. Editing is strictly narrower than deploying: `_pv_should_deploy` returns
# 0 for a missing destination (nothing to lose by creating it), but there is nothing to
# clean in a file that does not exist, and a file of unknown provenance must never be
# rewritten by a cleanup pass the consumer never asked for.
_pv_is_ours() {
    local key="$1" file="$2" known dst_hash

    [[ -f "$file" ]] || return 1
    known="$(_pv_known_hash "$key" 2>/dev/null)" || return 1
    [[ -n "$known" ]] || return 1
    dst_hash="$(_pv_sha256 "$file")" || return 1
    [[ "$dst_hash" == "$known" ]]
}

# Record the hash a destination will carry after a successful copy.
_pv_record() {
    local key="$1" src="$2" digest
    digest="$(_pv_sha256 "$src")" || return 0
    [[ -n "$digest" ]] || return 0
    printf '%s\t%s\n' "$key" "$digest" >> "$_PV_STAGED"
}

# Stage a tombstone for a path the project deleted.
_pv_tombstone() {
    local key="$1"
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    printf '%s\n' "$key" >> "$_PV_NEWTOMBS"
    printf '%s\n' "$key" >> "$_PV_TOMBS"
    _PV_TOMBSTONED=$((_PV_TOMBSTONED + 1))
}

# Deploy one file through the provenance guard.
#   $1 project-relative key   $2 source file   $3 destination file
# Honours DRY_RUN (reports, writes nothing). Never returns non-zero for a skip —
# a skip is a normal outcome, not a failure.
_pv_deploy_file() {
    local key="$1" src="$2" dst="$3"
    local reason

    if ! reason="$(_pv_should_deploy "$key" "$dst")"; then
        _PV_SKIPPED=$((_PV_SKIPPED + 1))
        if [[ "${DRY_RUN:-false}" == "true" ]]; then
            info "    Would skip $key — $reason"
        else
            warn "    Skipped $key — $reason"
        fi
        return 0
    fi

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        _PV_DEPLOYED=$((_PV_DEPLOYED + 1))
        return 0
    fi

    mkdir -p "$(dirname "$dst")"
    if cp "$src" "$dst" 2>/dev/null; then
        _pv_record "$key" "$src"
        _PV_DEPLOYED=$((_PV_DEPLOYED + 1))
    else
        warn "    Failed to copy $key"
    fi
    return 0
}

# Prepare a destination directory for file-by-file deploys.
#   $1 source dir   $2 destination dir
# Drops a symlinked destination (older deployments linked instead of copying — writing
# through it would edit set-core's own tree) and reports whether deploying is meaningful.
# Returns 1 when source and destination are the same directory (self-deploy).
_pv_prepare_dir() {
    local src_dir="$1" dst_dir="$2"

    if [[ -L "$dst_dir" ]]; then
        if [[ "${DRY_RUN:-false}" == "true" ]]; then
            info "    Would replace symlink: $dst_dir"
        else
            rm -f "$dst_dir"
        fi
    fi

    if [[ -d "$dst_dir" ]] && [[ "$(realpath "$src_dir" 2>/dev/null)" == "$(realpath "$dst_dir" 2>/dev/null)" ]]; then
        return 1
    fi
    return 0
}

# Deploy a whole source tree through the guard, file by file.
#   $1 source dir   $2 destination dir   $3 project root   [$4 key prefix override]
# The key is derived from the destination path relative to the project root, so the
# ledger reads as the consumer sees the tree.
_pv_deploy_tree() {
    local src_dir="$1" dst_dir="$2" project_path="$3"

    [[ -d "$src_dir" ]] || return 0

    # Drops a stale symlink; returns 1 when deploying onto ourselves (a no-op, not an error).
    _pv_prepare_dir "$src_dir" "$dst_dir" || return 0

    [[ "${DRY_RUN:-false}" == "true" ]] || mkdir -p "$dst_dir"

    local src_file rel dst_file key
    while IFS= read -r -d '' src_file; do
        rel="${src_file#"$src_dir"/}"
        dst_file="$dst_dir/$rel"
        key="${dst_file#"$project_path"/}"
        _pv_deploy_file "$key" "$src_file" "$dst_file"
    done < <(find "$src_dir" -type f -print0 2>/dev/null)
}

# Flush staged hashes into the ledger and report the session totals.
# Merges with any existing entries so keys from other deploy phases survive.
_pv_end() {
    local project_path="${_PV_PROJECT:-}"
    local ledger

    if [[ -n "$project_path" ]] && [[ "${DRY_RUN:-false}" != "true" ]] \
        && { [[ -s "${_PV_STAGED:-/nonexistent}" ]] || [[ -s "${_PV_NEWTOMBS:-/nonexistent}" ]]; } \
        && command -v python3 &>/dev/null; then
        ledger="$(_pv_ledger_path "$project_path")"
        mkdir -p "$(dirname "$ledger")"
        python3 -c "
import json, os, sys
from datetime import datetime, timezone

ledger_path, staged_path, tombs_path = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
if os.path.isfile(ledger_path):
    try:
        with open(ledger_path) as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            data = loaded
    except (OSError, ValueError):
        data = {}

files = data.get('files')
if not isinstance(files, dict):
    files = {}
tombstones = data.get('tombstones')
if not isinstance(tombstones, list):
    tombstones = []
tombstones = {t for t in tombstones if isinstance(t, str)}

if os.path.isfile(staged_path):
    with open(staged_path) as f:
        for line in f:
            line = line.rstrip('\n')
            if not line or '\t' not in line:
                continue
            key, digest = line.split('\t', 1)
            files[key] = digest
            tombstones.discard(key)

if os.path.isfile(tombs_path):
    with open(tombs_path) as f:
        for line in f:
            key = line.rstrip('\n')
            if not key:
                continue
            tombstones.add(key)
            files.pop(key, None)

data['version'] = 2
data['_help'] = (
    \"Written by 'set-project init'. 'files' maps a project-relative path to the sha256 \"
    \"of the content set-core deployed there; a file whose hash still matches is treated \"
    \"as untouched and may be updated, one that differs belongs to the project and is left \"
    \"alone. 'tombstones' lists paths the project deleted on purpose - set-core will not \"
    \"recreate them. To accept the framework version of a tombstoned path again, remove its \"
    \"entry from the 'tombstones' list and re-run the init.\"
)
data['files'] = dict(sorted(files.items()))
data['tombstones'] = sorted(tombstones)
data['updated'] = datetime.now(timezone.utc).isoformat(timespec='seconds')

tmp = ledger_path + '.tmp'
with open(tmp, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
os.replace(tmp, ledger_path)
" "$ledger" "$_PV_STAGED" "$_PV_NEWTOMBS" 2>/dev/null \
            || warn "  Failed to update deploy ledger: $ledger"
    fi

    rm -f "${_PV_KNOWN:-}" "${_PV_STAGED:-}" "${_PV_TOMBS:-}" "${_PV_NEWTOMBS:-}" \
          "${_PV_GITDEL:-}" 2>/dev/null || true
    unset _PV_KNOWN _PV_STAGED _PV_TOMBS _PV_NEWTOMBS _PV_GITDEL _PV_PROJECT
}

# "Deployed" under a real run, "Would deploy" under --dry-run. Keeps the log honest:
# a dry run must never claim it wrote something.
_pv_verb() {
    if [[ "${DRY_RUN:-false}" == "true" ]]; then printf 'Would deploy'; else printf 'Deployed'; fi
}

# Human-readable summary of the session; call before _pv_end.
_pv_report_skips() {
    local label="$1"
    if [[ "${_PV_SKIPPED:-0}" -gt 0 ]]; then
        if [[ "${DRY_RUN:-false}" == "true" ]]; then
            info "  $label: would deploy ${_PV_DEPLOYED:-0}, would skip ${_PV_SKIPPED} project-owned file(s)"
        else
            info "  $label: deployed ${_PV_DEPLOYED:-0}, preserved ${_PV_SKIPPED} project-owned file(s)"
        fi
    fi
    if [[ "${_PV_TOMBSTONED:-0}" -gt 0 ]]; then
        info "  $label: recorded ${_PV_TOMBSTONED} tombstone(s) — files the project deleted are not being recreated"
        info "    (to accept the framework version again, remove the path from 'tombstones' in set/.deploy-manifest.json)"
    fi
}
