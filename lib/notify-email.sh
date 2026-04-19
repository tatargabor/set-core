#!/usr/bin/env bash
# Email notification via Resend API (curl-based, no dependencies)
#
# Usage:
#   source lib/notify-email.sh
#   send_email "Subject" "HTML body"
#   send_email "Subject" "HTML body" "override@to.com"
#
# Environment variables (from project .env):
#   RESEND_API_KEY  — required
#   RESEND_FROM     — sender address (required)
#   RESEND_TO       — recipient address (required)

_email_load_env() {
    # Load .env from current working directory (the project where orchestration runs)
    if [[ -f ".env" ]]; then
        # shellcheck disable=SC1090
        set -a
        source ".env"
        set +a
    fi
}

send_email() {
    local subject="$1"
    local body="$2"
    local to_override="${3:-}"

    _email_load_env

    local to="${to_override:-${RESEND_TO:-}}"

    if [[ -z "${RESEND_API_KEY:-}" ]]; then
        echo "[email] RESEND_API_KEY not set — skipping email" >&2
        return 1
    fi
    if [[ -z "$to" ]]; then
        echo "[email] RESEND_TO not set — skipping email" >&2
        return 1
    fi

    local from="${RESEND_FROM:-}"
    if [[ -z "$from" ]]; then
        echo "[email] RESEND_FROM not set — skipping email" >&2
        return 1
    fi

    # Build JSON payload
    local payload
    payload=$(jq -n \
        --arg from "$from" \
        --arg to "$to" \
        --arg subject "$subject" \
        --arg html "$body" \
        '{from: $from, to: [$to], subject: $subject, html: $html}')

    local response http_code
    response=$(curl -s -w "\n%{http_code}" \
        -X POST "https://api.resend.com/emails" \
        -H "Authorization: Bearer $RESEND_API_KEY" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>&1)

    http_code=$(echo "$response" | tail -1)
    local body_response
    body_response=$(echo "$response" | sed '$d')

    if [[ "$http_code" == "200" ]]; then
        local email_id
        email_id=$(echo "$body_response" | jq -r '.id // "unknown"' 2>/dev/null)
        echo "[email] Sent successfully (id: $email_id, to: $to)"
        return 0
    else
        echo "[email] Failed (HTTP $http_code): $body_response" >&2
        return 1
    fi
}

# Send orchestration summary email
send_summary_email() {
    local reason="${1:-completion}"  # completion, checkpoint, manual
    local project_name="${2:-$(basename "$(pwd)")}"
    # Default resolves via the Python resolver so the literal lives there.
    # Callers should pass an explicit path; this fallback exists for
    # legacy bash callsites and is best-effort.
    local _default_state_file
    if command -v python3 >/dev/null 2>&1; then
        _default_state_file="$(python3 -c 'import os, sys; sys.path.insert(0, "lib"); from set_orch.paths import LineagePaths; print(LineagePaths(os.getcwd()).state_file)' 2>/dev/null || printf 'state.json')"
    else
        _default_state_file="state.json"
    fi
    local state_file="${3:-$_default_state_file}"
    local coverage_summary="${4:-}"  # optional coverage summary string

    _email_load_env

    if [[ -z "${RESEND_API_KEY:-}" || -z "${RESEND_TO:-}" ]]; then
        return 0  # silently skip if not configured
    fi

    local subject="[set-core] $project_name — orchestration $reason"
    local html=""

    # Header
    html+="<h2>Orchestration $reason: $project_name</h2>"
    html+="<p><strong>Date:</strong> $(date '+%Y-%m-%d %H:%M:%S')</p>"

    if [[ -f "$state_file" ]]; then
        local status total_changes completed tokens
        status=$(jq -r '.status // "unknown"' "$state_file")
        total_changes=$(jq '.changes | length' "$state_file")
        completed=$(jq '[.changes[] | select(.status == "done" or .status == "merged")] | length' "$state_file")
        tokens=$(jq '[.changes[].tokens_used // 0] | add // 0' "$state_file")

        html+="<h3>Summary</h3>"
        html+="<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
        html+="<tr><td><strong>Status</strong></td><td>$status</td></tr>"
        html+="<tr><td><strong>Changes</strong></td><td>$completed / $total_changes complete</td></tr>"
        html+="<tr><td><strong>Total Tokens</strong></td><td>$tokens</td></tr>"
        html+="</table>"

        # Per-change details
        html+="<h3>Changes</h3>"
        html+="<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
        html+="<tr style='background:#f0f0f0;'><th>Change</th><th>Status</th><th>Tests</th><th>Tokens</th></tr>"

        while IFS=$'\t' read -r name cstatus test_res ctokens; do
            local color="#fff"
            case "$cstatus" in
                done|merged) color="#d4edda" ;;
                failed|merge-blocked) color="#f8d7da" ;;
                running|verifying) color="#fff3cd" ;;
            esac
            html+="<tr style='background:$color;'><td>$name</td><td>$cstatus</td><td>${test_res}</td><td>$ctokens</td></tr>"
        done < <(jq -r '.changes[] | "\(.name)\t\(.status)\t\(.test_result // "-")\t\(.tokens_used // 0)"' "$state_file")

        html+="</table>"

        # Per-phase breakdown when milestones exist
        local has_phases
        has_phases=$(jq 'has("phases")' "$state_file" 2>/dev/null)
        if [[ "$has_phases" == "true" ]]; then
            html+="<h3>Phase Breakdown</h3>"
            html+="<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
            html+="<tr style='background:#f0f0f0;'><th>Phase</th><th>Status</th><th>Changes</th><th>Tokens</th></tr>"
            while IFS=$'\t' read -r pnum pstatus; do
                [[ -z "$pnum" ]] && continue
                local ph_merged ph_total ph_tokens
                ph_total=$(jq --argjson p "$pnum" '[.changes[] | select(.phase == $p)] | length' "$state_file" 2>/dev/null || echo 0)
                ph_merged=$(jq --argjson p "$pnum" '[.changes[] | select(.phase == $p and (.status == "merged" or .status == "done"))] | length' "$state_file" 2>/dev/null || echo 0)
                ph_tokens=$(jq --argjson p "$pnum" '[.changes[] | select(.phase == $p) | .tokens_used // 0] | add // 0' "$state_file" 2>/dev/null || echo 0)
                local color="#fff"
                [[ "$pstatus" == "completed" ]] && color="#d4edda"
                [[ "$pstatus" == "running" ]] && color="#fff3cd"
                html+="<tr style='background:$color;'><td>Phase $pnum</td><td>$pstatus</td><td>$ph_merged/$ph_total</td><td>$ph_tokens</td></tr>"
            done < <(jq -r '.phases | to_entries | sort_by(.key | tonumber) | .[] | "\(.key)\t\(.value.status // "pending")"' "$state_file" 2>/dev/null || true)
            html+="</table>"
        fi
    fi

    # Coverage summary (if provided by caller)
    if [[ -n "$coverage_summary" ]]; then
        html+="<h3>Requirement Coverage</h3>"
        html+="<p style='font-family:monospace;background:#f5f5f5;padding:8px;'>$coverage_summary</p>"
    fi

    # Orchestration summary.md if exists
    if [[ -f "orchestration-summary.md" ]]; then
        html+="<h3>Full Summary</h3>"
        html+="<pre style='background:#f5f5f5;padding:12px;font-size:13px;overflow:auto;'>"
        html+="$(sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g' orchestration-summary.md)"
        html+="</pre>"
    fi

    send_email "$subject" "$html"
}
