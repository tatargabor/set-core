#!/usr/bin/env bash
# lib/orchestration/reporter.sh — HTML report generator for orchestration dashboard
# Sourced by bin/wt-orchestrate after digest.sh.
# Provides: generate_report()

REPORT_OUTPUT_PATH="wt/orchestration/report.html"

# ─── Entry Point ────────────────────────────────────────────────────

generate_report() {
    local html=""

    html+="$(render_html_wrapper_open)"
    html+="$(render_digest_section)"
    html+="$(render_plan_section)"
    html+="$(render_execution_section)"
    html+="$(render_coverage_section)"
    html+="$(render_html_wrapper_close)"

    # Atomic write: tmp file + mv
    mkdir -p "$(dirname "$REPORT_OUTPUT_PATH")"
    local tmp
    tmp=$(mktemp)
    printf '%s' "$html" > "$tmp"
    mv "$tmp" "$REPORT_OUTPUT_PATH"
}

# ─── HTML Wrapper ───────────────────────────────────────────────────

render_html_wrapper_open() {
    cat <<'HTML_HEAD'
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="15">
<title>Orchestration Report</title>
<style>
  :root { color-scheme: dark; }
  body { background: #1e1e1e; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace; margin: 0; padding: 20px; }
  h1 { color: #fff; border-bottom: 2px solid #444; padding-bottom: 8px; }
  h2 { color: #ccc; margin-top: 32px; border-bottom: 1px solid #333; padding-bottom: 4px; }
  h3 { color: #aaa; margin-top: 20px; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; }
  th, td { border: 1px solid #444; padding: 8px 12px; text-align: left; }
  th { background: #2a2a2a; color: #ccc; font-weight: 600; }
  tr:nth-child(even) { background: #252525; }
  .status-merged, .status-done { color: #4caf50; }
  .status-running, .status-verifying { color: #ff9800; }
  .status-failed { color: #f44336; }
  .status-merge-blocked, .status-blocked { color: #e91e63; }
  .status-pending, .status-planned { color: #9e9e9e; }
  .status-uncovered { color: #ff5722; font-weight: bold; }
  .gate-pass { color: #4caf50; }
  .gate-fail { color: #f44336; }
  .gate-na { color: #666; }
  .coverage-bar { background: #333; border-radius: 4px; height: 16px; overflow: hidden; display: inline-block; width: 120px; vertical-align: middle; }
  .coverage-fill { height: 100%; background: #4caf50; }
  details { margin: 8px 0; }
  summary { cursor: pointer; padding: 4px; color: #ccc; }
  .not-available { color: #666; font-style: italic; }
  .footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid #333; color: #666; font-size: 12px; }
</style>
</head>
<body>
<h1>Orchestration Report</h1>
HTML_HEAD
}

render_html_wrapper_close() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    cat <<HTML_FOOT
<div class="footer">Generated: $timestamp | Auto-refreshes every 15s</div>
</body>
</html>
HTML_FOOT
}

# ─── Digest Section ─────────────────────────────────────────────────

render_digest_section() {
    echo "<h2>Spec Digest</h2>"

    if [[ ! -d "$DIGEST_DIR" || ! -f "$DIGEST_DIR/index.json" ]]; then
        echo '<p class="not-available">Not available — run <code>wt-orchestrate digest</code> first.</p>'
        return 0
    fi

    # Spec source info
    local spec_dir source_hash file_count timestamp
    spec_dir=$(jq -r '.spec_base_dir // "unknown"' "$DIGEST_DIR/index.json")
    source_hash=$(jq -r '.source_hash // "unknown"' "$DIGEST_DIR/index.json")
    file_count=$(jq -r '.file_count // 0' "$DIGEST_DIR/index.json")
    timestamp=$(jq -r '.timestamp // "unknown"' "$DIGEST_DIR/index.json")

    echo "<p><strong>Source:</strong> $spec_dir ($file_count files) | <strong>Hash:</strong> ${source_hash:0:12} | <strong>Digested:</strong> $timestamp</p>"

    # Requirements count
    if [[ -f "$DIGEST_DIR/requirements.json" ]]; then
        local req_count
        req_count=$(jq '[.requirements[] | select(.status != "removed")] | length' "$DIGEST_DIR/requirements.json" 2>/dev/null || echo 0)
        echo "<p><strong>Requirements:</strong> $req_count</p>"
    fi

    # Domain table
    if [[ -d "$DIGEST_DIR/domains" ]]; then
        echo "<h3>Domains</h3>"
        echo "<table><tr><th>Domain</th><th>Requirements</th></tr>"
        local domains
        if [[ -f "$DIGEST_DIR/requirements.json" ]]; then
            domains=$(jq -r '[.requirements[] | select(.status != "removed") | .domain // "unknown"] | unique | .[]' "$DIGEST_DIR/requirements.json" 2>/dev/null || true)
        fi
        while IFS= read -r domain; do
            [[ -z "$domain" ]] && continue
            local domain_count
            domain_count=$(jq --arg d "$domain" '[.requirements[] | select(.domain == $d and .status != "removed")] | length' "$DIGEST_DIR/requirements.json" 2>/dev/null || echo 0)
            echo "<tr><td>$domain</td><td>$domain_count</td></tr>"
        done <<< "$domains"
        echo "</table>"
    fi

    # Ambiguities — table with resolution status
    if [[ -f "$DIGEST_DIR/ambiguities.json" ]]; then
        local amb_count
        amb_count=$(jq '.ambiguities | length' "$DIGEST_DIR/ambiguities.json" 2>/dev/null || echo 0)
        if [[ "$amb_count" -gt 0 ]]; then
            echo "<h3>Ambiguities ($amb_count)</h3>"
            echo "<table><tr><th>ID</th><th>Type</th><th>Description</th><th>Resolution</th><th>Note</th><th>By</th></tr>"
            jq -r '.ambiguities[] |
                (.resolution // "UNRESOLVED") as $res |
                (if $res == "fixed" then "background:#2e4a2e"
                 elif $res == "deferred" or $res == "planner-resolved" then "background:#2a3a4e"
                 elif $res == "ignored" then "background:#3a3a3a"
                 else "background:#4e2a2a" end) as $color |
                "<tr style=\"\($color)\"><td>\(.id // "-")</td><td>\(.type // "-")</td><td>\(.description // "-")</td><td>\($res)</td><td>\(.resolution_note // "")</td><td>\(.resolved_by // "-")</td></tr>"
            ' "$DIGEST_DIR/ambiguities.json" 2>/dev/null || true
            echo "</table>"
        fi
    fi
}

# ─── Plan Section ───────────────────────────────────────────────────

render_plan_section() {
    echo "<h2>Plan</h2>"

    local plan_file="${PLAN_FILENAME:-orchestration-plan.json}"
    if [[ ! -f "$plan_file" ]]; then
        echo '<p class="not-available">No plan generated yet.</p>'
        return 0
    fi

    local total_changes
    total_changes=$(jq '.changes | length' "$plan_file" 2>/dev/null || echo 0)
    echo "<p><strong>Changes:</strong> $total_changes</p>"

    echo "<table>"
    echo "<tr><th>Change</th><th>REQs</th><th>Dependencies</th><th>Status</th></tr>"

    while IFS=$'\t' read -r name req_count deps; do
        [[ -z "$name" ]] && continue
        # Get status from state if available
        local status="planned"
        if [[ -f "$STATE_FILENAME" ]]; then
            status=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .status // "planned"' "$STATE_FILENAME" 2>/dev/null || echo "planned")
        fi
        [[ "$deps" == "null" || -z "$deps" ]] && deps="-"
        echo "<tr><td>$name</td><td>$req_count</td><td>$deps</td><td><span class=\"status-$status\">$status</span></td></tr>"
    done < <(jq -r '.changes[] | "\(.name)\t\(.requirements // [] | length)\t\(.depends_on // [] | join(", "))"' "$plan_file" 2>/dev/null || true)

    echo "</table>"
}

# ─── Execution Section ──────────────────────────────────────────────

render_execution_section() {
    echo "<h2>Execution</h2>"

    if [[ ! -f "$STATE_FILENAME" ]]; then
        echo '<p class="not-available">No execution state.</p>'
        return 0
    fi

    local orch_status
    orch_status=$(jq -r '.status // "unknown"' "$STATE_FILENAME" 2>/dev/null || echo "unknown")
    echo "<p><strong>Status:</strong> <span class=\"status-$orch_status\">$orch_status</span></p>"

    # Change timeline
    echo "<table>"
    echo "<tr><th>Change</th><th>Status</th><th>Tokens</th><th>Test</th><th>Smoke</th></tr>"

    while IFS=$'\t' read -r name status tokens test_res smoke_res; do
        [[ -z "$name" ]] && continue

        local test_class="gate-na" smoke_class="gate-na"
        local test_display="-" smoke_display="-"

        if [[ "$test_res" == "pass" ]]; then
            test_class="gate-pass"; test_display="&#10003;"
        elif [[ "$test_res" == "fail" ]]; then
            test_class="gate-fail"; test_display="&#10007;"
        fi

        if [[ "$smoke_res" == "pass" ]]; then
            smoke_class="gate-pass"; smoke_display="&#10003;"
        elif [[ "$smoke_res" == "fail" ]]; then
            smoke_class="gate-fail"; smoke_display="&#10007;"
        fi

        echo "<tr>"
        echo "<td>$name</td>"
        echo "<td><span class=\"status-$status\">$status</span></td>"
        echo "<td>$tokens</td>"
        echo "<td><span class=\"$test_class\">$test_display</span></td>"
        echo "<td><span class=\"$smoke_class\">$smoke_display</span></td>"
        echo "</tr>"
    done < <(jq -r '.changes[] | "\(.name)\t\(.status)\t\(.tokens_used // 0)\t\(.test_result // "-")\t\(.smoke_result // "-")"' "$STATE_FILENAME" 2>/dev/null || true)

    echo "</table>"
}

# ─── Coverage Section ───────────────────────────────────────────────

render_coverage_section() {
    echo "<h2>Requirement Coverage</h2>"

    if [[ ! -f "$DIGEST_DIR/requirements.json" || ! -f "$DIGEST_DIR/coverage.json" ]]; then
        echo '<p class="not-available">Not available — no digest or coverage data.</p>'
        return 0
    fi

    # Group by domain using collapsible details
    local domains
    domains=$(jq -r '[.requirements[] | select(.status != "removed") | .domain // "unknown"] | unique | .[]' "$DIGEST_DIR/requirements.json" 2>/dev/null || true)

    local grand_total=0 grand_covered=0

    while IFS= read -r domain; do
        [[ -z "$domain" ]] && continue

        local domain_reqs domain_total=0 domain_covered=0
        local rows=""

        while IFS=$'\t' read -r req_id title; do
            [[ -z "$req_id" ]] && continue
            domain_total=$((domain_total + 1))
            grand_total=$((grand_total + 1))

            local cov_change cov_status effective_status status_class
            cov_change=$(jq -r --arg id "$req_id" '.coverage[$id].change // empty' "$DIGEST_DIR/coverage.json" 2>/dev/null || true)

            if [[ -z "$cov_change" ]]; then
                effective_status="uncovered"
            elif [[ -f "$STATE_FILENAME" ]]; then
                local state_status
                state_status=$(jq -r --arg n "$cov_change" '.changes[] | select(.name == $n) | .status // "planned"' "$STATE_FILENAME" 2>/dev/null || echo "planned")
                case "$state_status" in
                    merged|done) effective_status="merged"; domain_covered=$((domain_covered + 1)); grand_covered=$((grand_covered + 1)) ;;
                    failed) effective_status="failed" ;;
                    merge-blocked) effective_status="blocked" ;;
                    running|verifying) effective_status="running" ;;
                    *) effective_status="planned" ;;
                esac
            else
                effective_status="planned"
            fi

            rows+="<tr><td>$req_id</td><td>$title</td><td>$cov_change</td><td><span class=\"status-$effective_status\">$effective_status</span></td></tr>"
        done < <(jq -r --arg d "$domain" '.requirements[] | select(.domain == $d and .status != "removed") | "\(.id)\t\(.title // "-")"' "$DIGEST_DIR/requirements.json" 2>/dev/null || true)

        local pct=0
        if [[ "$domain_total" -gt 0 ]]; then
            pct=$((domain_covered * 100 / domain_total))
        fi

        echo "<details>"
        echo "<summary><strong>$domain</strong> — $domain_covered/$domain_total ($pct%) <span class=\"coverage-bar\"><span class=\"coverage-fill\" style=\"width:${pct}%\"></span></span></summary>"
        echo "<table><tr><th>REQ</th><th>Title</th><th>Change</th><th>Status</th></tr>"
        echo "$rows"
        echo "</table>"
        echo "</details>"
    done <<< "$domains"

    # Summary
    local grand_pct=0
    if [[ "$grand_total" -gt 0 ]]; then
        grand_pct=$((grand_covered * 100 / grand_total))
    fi
    echo "<p><strong>Total:</strong> $grand_covered/$grand_total requirements merged ($grand_pct%)</p>"
}
