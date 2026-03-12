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
  .status-skipped { color: #ffc107; }
  .status-pending, .status-planned { color: #9e9e9e; }
  .status-uncovered { color: #ff5722; font-weight: bold; }
  .gate-pass { color: #4caf50; }
  .gate-fail { color: #f44336; }
  .gate-na { color: #666; }
  .coverage-bar { background: #333; border-radius: 4px; height: 16px; overflow: hidden; display: inline-block; width: 120px; vertical-align: middle; }
  .coverage-fill { height: 100%; background: #4caf50; float: left; }
  .coverage-fill-inprogress { height: 100%; background: #ff9800; float: left; }
  .coverage-summary { background: #252525; border: 1px solid #444; border-radius: 8px; padding: 16px 20px; margin: 16px 0; }
  .coverage-summary p { margin: 8px 0 0 0; font-size: 14px; }
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

    # E2E mode
    local e2e_mode
    e2e_mode=$(jq -r '.directives.e2e_mode // "per_change"' "$STATE_FILENAME" 2>/dev/null || echo "per_change")
    echo "<p><strong>E2E mode:</strong> $e2e_mode</p>"

    # Change timeline
    echo "<table>"
    if [[ "$e2e_mode" == "phase_end" ]]; then
        echo "<tr><th>Change</th><th>Status</th><th>Duration</th><th>Tokens</th><th>Test</th><th>Smoke</th></tr>"
    else
        echo "<tr><th>Change</th><th>Status</th><th>Duration</th><th>Tokens</th><th>Test</th><th>E2E</th><th>Smoke</th></tr>"
    fi

    local total_tokens=0 total_duration_s=0 total_tests=0

    while IFS=$'\t' read -r name status tokens test_res e2e_res smoke_res started_at completed_at test_stats smoke_sc_count smoke_sc_dir e2e_sc_count e2e_sc_dir; do
        [[ -z "$name" ]] && continue

        local test_class="gate-na" smoke_class="gate-na" e2e_class="gate-na"
        local test_display="-" smoke_display="-" e2e_display="-"

        if [[ "$test_res" == "pass" ]]; then
            test_class="gate-pass"; test_display="&#10003;"
        elif [[ "$test_res" == "fail" ]]; then
            test_class="gate-fail"; test_display="&#10007;"
        fi

        if [[ "$e2e_res" == "pass" ]]; then
            e2e_class="gate-pass"; e2e_display="&#10003;"
        elif [[ "$e2e_res" == "fail" ]]; then
            e2e_class="gate-fail"; e2e_display="&#10007;"
        elif [[ "$e2e_res" == "skipped" || "$e2e_res" == "skip" ]]; then
            e2e_display="skip"
        fi

        if [[ "$smoke_res" == "pass" || "$smoke_res" == "fixed" ]]; then
            smoke_class="gate-pass"; smoke_display="&#10003;"
        elif [[ "$smoke_res" == "fail" ]]; then
            smoke_class="gate-fail"; smoke_display="&#10007;"
        elif [[ "$smoke_res" == "skip_merged" ]]; then
            smoke_display="<span title=\"Skipped — already merged from previous phase\">-</span>"
        elif [[ "$smoke_res" == "skip" ]]; then
            smoke_display="<span title=\"Skipped — no smoke command configured\">-</span>"
        fi

        # Append camera icon if screenshots exist
        if [[ "${smoke_sc_count:-0}" -gt 0 && -n "${smoke_sc_dir:-}" && "$smoke_sc_dir" != "null" && "$smoke_sc_dir" != "0" ]]; then
            smoke_display="${smoke_display} <a href=\"../../${smoke_sc_dir}\" title=\"${smoke_sc_count} screenshots\" style=\"text-decoration:none\">&#128247;</a>"
        fi

        if [[ "${e2e_sc_count:-0}" -gt 0 && -n "${e2e_sc_dir:-}" && "$e2e_sc_dir" != "null" && "$e2e_sc_dir" != "0" ]]; then
            e2e_display="${e2e_display} <a href=\"../../${e2e_sc_dir}\" title=\"${e2e_sc_count} screenshots\" style=\"text-decoration:none\">&#128247;</a>"
        fi

        # Duration calculation
        local duration_display="-"
        if [[ -n "$started_at" && "$started_at" != "null" ]]; then
            local start_epoch end_epoch dur_s
            start_epoch=$(date -d "$started_at" +%s 2>/dev/null || echo 0)
            if [[ -n "$completed_at" && "$completed_at" != "null" ]]; then
                end_epoch=$(date -d "$completed_at" +%s 2>/dev/null || echo 0)
            else
                end_epoch=$(date +%s)
            fi
            if [[ "$start_epoch" -gt 0 ]]; then
                dur_s=$((end_epoch - start_epoch))
                total_duration_s=$((total_duration_s + dur_s))
                local dur_m=$((dur_s / 60)) dur_rem=$((dur_s % 60))
                duration_display="${dur_m}m${dur_rem}s"
            fi
        fi

        # Test stats (if stored)
        local test_stat_display=""
        if [[ -n "$test_stats" && "$test_stats" != "null" && "$test_stats" != "{}" ]]; then
            local t_pass t_fail t_total
            t_pass=$(echo "$test_stats" | jq -r '.passed // 0' 2>/dev/null || echo 0)
            t_fail=$(echo "$test_stats" | jq -r '.failed // 0' 2>/dev/null || echo 0)
            t_total=$((t_pass + t_fail))
            if [[ "$t_total" -gt 0 ]]; then
                test_display="${test_display} <small>${t_pass}/${t_total}</small>"
                total_tests=$((total_tests + t_total))
            fi
        fi

        # Token formatting
        local token_display="$tokens"
        if [[ "$tokens" -gt 999999 ]]; then
            token_display="$(echo "scale=1; $tokens / 1000000" | bc)M"
        elif [[ "$tokens" -gt 999 ]]; then
            token_display="$(echo "scale=0; $tokens / 1000" | bc)K"
        fi
        total_tokens=$((total_tokens + tokens))

        # Skip reason tooltip
        local status_html="<span class=\"status-$status\">$status</span>"
        if [[ "$status" == "skipped" ]]; then
            local skip_reason
            skip_reason=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .skip_reason // empty' "$STATE_FILENAME" 2>/dev/null)
            if [[ -n "$skip_reason" ]]; then
                status_html="<span class=\"status-$status\" title=\"$skip_reason\">$status</span> <small>($skip_reason)</small>"
            fi
        fi

        echo "<tr>"
        echo "<td>$name</td>"
        echo "<td>$status_html</td>"
        echo "<td>$duration_display</td>"
        echo "<td>$token_display</td>"
        echo "<td><span class=\"$test_class\">$test_display</span></td>"
        if [[ "$e2e_mode" != "phase_end" ]]; then
            echo "<td><span class=\"$e2e_class\">$e2e_display</span></td>"
        fi
        echo "<td><span class=\"$smoke_class\">$smoke_display</span></td>"
        echo "</tr>"
    done < <(jq -r '.changes[] | "\(.name)\t\(.status)\t\(.tokens_used // 0)\t\(.test_result // "-")\t\(.e2e_result // "-")\t\(.smoke_result // "-")\t\(.started_at // "null")\t\(.completed_at // "null")\t\(.test_stats // {} | tostring)\t\(.smoke_screenshot_count // 0)\t\(.smoke_screenshot_dir // "null")\t\(.e2e_screenshot_count // 0)\t\(.e2e_screenshot_dir // "null")"' "$STATE_FILENAME" 2>/dev/null || true)

    # Summary row
    local total_token_display="$total_tokens"
    if [[ "$total_tokens" -gt 999999 ]]; then
        total_token_display="$(echo "scale=1; $total_tokens / 1000000" | bc)M"
    elif [[ "$total_tokens" -gt 999 ]]; then
        total_token_display="$(echo "scale=0; $total_tokens / 1000" | bc)K"
    fi
    local total_dur_m=$((total_duration_s / 60))

    local summary_colspan=2
    [[ "$e2e_mode" != "phase_end" ]] && summary_colspan=3

    echo "<tr style=\"border-top:2px solid #666;font-weight:bold\">"
    echo "<td>Total</td><td></td><td>${total_dur_m}m</td><td>$total_token_display</td>"
    if [[ "$total_tests" -gt 0 ]]; then
        echo "<td colspan=\"$summary_colspan\">$total_tests tests</td>"
    else
        echo "<td colspan=\"$summary_colspan\"></td>"
    fi
    echo "</tr>"
    echo "</table>"

    # Smoke screenshot gallery (collapsible)
    local any_smoke_sc
    any_smoke_sc=$(jq '[.changes[] | select((.smoke_screenshot_count // 0) > 0)] | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
    if [[ "$any_smoke_sc" -gt 0 ]]; then
        echo "<details><summary>Smoke Screenshots</summary>"
        echo '<div style="margin:12px 0">'
        while IFS=$'\t' read -r sc_name sc_dir sc_count; do
            [[ -z "$sc_name" || "$sc_count" -eq 0 ]] && continue
            echo "<h4>$sc_name ($sc_count images)</h4>"
            if [[ -d "$sc_dir" ]]; then
                echo '<div style="display:flex;flex-wrap:wrap;gap:8px">'
                local img_count=0
                # Show attempt subdirs in reverse order (latest first)
                while IFS= read -r attempt_dir; do
                    [[ -z "$attempt_dir" || ! -d "$attempt_dir" ]] && continue
                    local attempt_name
                    attempt_name=$(basename "$attempt_dir")
                    while IFS= read -r png; do
                        [[ -z "$png" ]] && continue
                        [[ $img_count -ge 8 ]] && break 2
                        local rel_path="../../$png"
                        local fname
                        fname=$(basename "$png")
                        echo "<div style=\"text-align:center\">"
                        echo "<a href=\"$rel_path\" target=\"_blank\"><img src=\"$rel_path\" style=\"max-width:320px;max-height:200px;border:1px solid #444;border-radius:4px\" alt=\"$fname\"></a>"
                        echo "<br><small style=\"color:#888\">$attempt_name/$fname</small>"
                        echo "</div>"
                        img_count=$((img_count + 1))
                    done < <(find "$attempt_dir" -name "*.png" 2>/dev/null | sort)
                done < <(find "$sc_dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort -r)
                echo "</div>"
            fi
        done < <(jq -r '.changes[] | select((.smoke_screenshot_count // 0) > 0) | "\(.name)\t\(.smoke_screenshot_dir)\t\(.smoke_screenshot_count)"' "$STATE_FILENAME" 2>/dev/null || true)
        echo "</div></details>"
    fi

    # E2E screenshot gallery (collapsible)
    local any_e2e_sc
    any_e2e_sc=$(jq '[.changes[] | select((.e2e_screenshot_count // 0) > 0)] | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
    if [[ "$any_e2e_sc" -gt 0 ]]; then
        echo "<details><summary>E2E Screenshots</summary>"
        echo '<div style="margin:12px 0">'
        while IFS=$'\t' read -r sc_name sc_dir sc_count; do
            [[ -z "$sc_name" || "$sc_count" -eq 0 ]] && continue
            echo "<h4>$sc_name ($sc_count images)</h4>"
            if [[ -d "$sc_dir" ]]; then
                echo '<div style="display:flex;flex-wrap:wrap;gap:8px">'
                local img_count=0
                while IFS= read -r png; do
                    [[ -z "$png" ]] && continue
                    [[ $img_count -ge 8 ]] && break
                    local rel_path="../../$png"
                    local fname
                    fname=$(basename "$png")
                    echo "<div style=\"text-align:center\">"
                    echo "<a href=\"$rel_path\" target=\"_blank\"><img src=\"$rel_path\" style=\"max-width:320px;max-height:200px;border:1px solid #444;border-radius:4px\" alt=\"$fname\"></a>"
                    echo "<br><small style=\"color:#888\">$fname</small>"
                    echo "</div>"
                    img_count=$((img_count + 1))
                done < <(find "$sc_dir" -name "*.png" 2>/dev/null | sort | head -8)
                echo "</div>"
            fi
        done < <(jq -r '.changes[] | select((.e2e_screenshot_count // 0) > 0) | "\(.name)\t\(.e2e_screenshot_dir)\t\(.e2e_screenshot_count)"' "$STATE_FILENAME" 2>/dev/null || true)
        echo "</div></details>"
    fi

    # Phase-end E2E results (when e2e_mode=phase_end)
    local phase_e2e_count
    phase_e2e_count=$(jq '.phase_e2e_results // [] | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
    if [[ "$phase_e2e_count" -gt 0 ]]; then
        echo "<h3>Phase-End E2E Results</h3>"
        echo "<table>"
        echo "<tr><th>Phase</th><th>Result</th><th>Duration</th><th>Screenshots</th><th>Time</th></tr>"
        while IFS=$'\t' read -r pe_cycle pe_result pe_ms pe_sc_count pe_sc_dir pe_ts; do
            [[ -z "$pe_cycle" ]] && continue
            local pe_class="gate-pass"
            [[ "$pe_result" == "fail" ]] && pe_class="gate-fail"
            local pe_dur_s=$((pe_ms / 1000))
            local sc_display="-"
            if [[ "$pe_sc_count" -gt 0 && -n "$pe_sc_dir" && "$pe_sc_dir" != "null" ]]; then
                sc_display="<a href=\"../../$pe_sc_dir\" style=\"color:#64b5f6\">${pe_sc_count} images</a>"
            elif [[ "$pe_sc_count" -gt 0 ]]; then
                sc_display="${pe_sc_count} images"
            fi
            echo "<tr>"
            echo "<td>Cycle $pe_cycle</td>"
            echo "<td><span class=\"$pe_class\">$pe_result</span></td>"
            echo "<td>${pe_dur_s}s</td>"
            echo "<td>$sc_display</td>"
            echo "<td>$pe_ts</td>"
            echo "</tr>"
        done < <(jq -r '.phase_e2e_results[]? | "\(.cycle)\t\(.result)\t\(.duration_ms)\t\(.screenshot_count // 0)\t\(.screenshot_dir // "null")\t\(.timestamp // "-")"' "$STATE_FILENAME" 2>/dev/null || true)
        echo "</table>"

        # Inline screenshot gallery for the latest cycle
        local latest_sc_dir
        latest_sc_dir=$(jq -r '.phase_e2e_results[-1].screenshot_dir // ""' "$STATE_FILENAME" 2>/dev/null)
        if [[ -n "$latest_sc_dir" && -d "$latest_sc_dir" ]]; then
            local png_files
            png_files=$(find "$latest_sc_dir" -name "*.png" 2>/dev/null | sort | head -20)
            if [[ -n "$png_files" ]]; then
                echo "<details><summary>Screenshot Gallery (latest cycle)</summary>"
                echo '<div style="display:flex;flex-wrap:wrap;gap:8px;margin:12px 0">'
                while IFS= read -r png; do
                    local rel_path="../../$png"
                    local fname
                    fname=$(basename "$png")
                    echo "<div style=\"text-align:center\">"
                    echo "<a href=\"$rel_path\" target=\"_blank\"><img src=\"$rel_path\" style=\"max-width:320px;max-height:200px;border:1px solid #444;border-radius:4px\" alt=\"$fname\"></a>"
                    echo "<br><small style=\"color:#888\">$fname</small>"
                    echo "</div>"
                done <<< "$png_files"
                echo "</div></details>"
            fi
        fi
    fi
}

# ─── Coverage Section ───────────────────────────────────────────────

render_coverage_section() {
    echo '<h2>Requirement Coverage <label style="font-size:14px;font-weight:normal;margin-left:16px;cursor:pointer"><input type="checkbox" id="cov-all-toggle" onchange="toggleCovPhase()" checked> Include previous phases</label></h2>'
    echo '<script>function toggleCovPhase(){var c=document.getElementById("cov-all-toggle").checked;document.querySelectorAll("[data-phase=previous]").forEach(function(r){r.style.display=c?"":"none"});document.querySelectorAll(".cov-summary").forEach(function(e){var t=parseInt(e.dataset.total),m=parseInt(e.dataset.merged),i=parseInt(e.dataset.inprog),pm=parseInt(e.dataset.prevMerged);if(!c){m-=pm;t-=pm}var a=m+i,p=t>0?Math.round(a*100/t):0,mp=t>0?Math.round(m*100/t):0,ip=t>0?Math.round(i*100/t):0;e.querySelector(".cov-num").textContent=a+"/"+t+" requirements active ("+p+"%)";e.querySelector(".cov-detail").innerHTML="<span class=status-merged>"+m+" merged ("+mp+"%)</span> + <span class=status-running>"+i+" in-progress ("+ip+"%)</span>";e.querySelector(".coverage-fill").style.width=mp+"%";e.querySelector(".coverage-fill-inprogress").style.width=ip+"%";var uc=e.querySelector(".cov-uncovered");if(uc)uc.textContent=(t-a)+" uncovered"})}</script>'

    if [[ ! -f "$DIGEST_DIR/requirements.json" || ! -f "$DIGEST_DIR/coverage.json" ]]; then
        echo '<p class="not-available">Not available — no digest or coverage data.</p>'
        return 0
    fi

    # Group by domain using collapsible details
    local domains
    domains=$(jq -r '[.requirements[] | select(.status != "removed") | .domain // "unknown"] | unique | .[]' "$DIGEST_DIR/requirements.json" 2>/dev/null || true)

    local grand_total=0 grand_covered=0 grand_inprogress=0

    # First pass: collect data for summary + per-domain
    local -a domain_list=()
    local -A domain_totals=() domain_merged=() domain_inprogress=() domain_prev_merged=() domain_rows=()

    while IFS= read -r domain; do
        [[ -z "$domain" ]] && continue
        domain_list+=("$domain")
        domain_totals[$domain]=0
        domain_merged[$domain]=0
        domain_inprogress[$domain]=0
        domain_prev_merged[$domain]=0
        domain_rows[$domain]=""

        while IFS=$'\t' read -r req_id title; do
            [[ -z "$req_id" ]] && continue
            domain_totals[$domain]=$(( ${domain_totals[$domain]} + 1 ))
            grand_total=$((grand_total + 1))

            local cov_change effective_status cov_phase=""
            cov_change=$(jq -r --arg id "$req_id" '.coverage[$id].change // empty' "$DIGEST_DIR/coverage.json" 2>/dev/null || true)
            cov_phase=$(jq -r --arg id "$req_id" '.coverage[$id].phase // empty' "$DIGEST_DIR/coverage.json" 2>/dev/null || true)

            if [[ -z "$cov_change" ]]; then
                effective_status="uncovered"
            elif [[ "$cov_phase" == "previous" ]]; then
                # Previously merged from earlier orchestration phase
                effective_status="merged"
                domain_merged[$domain]=$(( ${domain_merged[$domain]} + 1 ))
                domain_prev_merged[$domain]=$(( ${domain_prev_merged[$domain]} + 1 ))
                grand_covered=$((grand_covered + 1))
            elif [[ -f "$STATE_FILENAME" ]]; then
                local state_status
                state_status=$(jq -r --arg n "$cov_change" '.changes[] | select(.name == $n) | .status // "planned"' "$STATE_FILENAME" 2>/dev/null || echo "planned")
                case "$state_status" in
                    merged|done)
                        effective_status="merged"
                        domain_merged[$domain]=$(( ${domain_merged[$domain]} + 1 ))
                        grand_covered=$((grand_covered + 1))
                        ;;
                    running|verifying)
                        effective_status="running"
                        domain_inprogress[$domain]=$(( ${domain_inprogress[$domain]} + 1 ))
                        grand_inprogress=$((grand_inprogress + 1))
                        ;;
                    failed) effective_status="failed" ;;
                    merge-blocked) effective_status="blocked" ;;
                    *) effective_status="planned" ;;
                esac
            else
                effective_status="planned"
            fi

            local row_phase_attr=""
            [[ "$cov_phase" == "previous" ]] && row_phase_attr=" data-phase=\"previous\" style=\"opacity:0.7\""
            domain_rows[$domain]+="<tr${row_phase_attr}><td>$req_id</td><td>$title</td><td>$cov_change</td><td><span class=\"status-$effective_status\">$effective_status</span></td></tr>"
        done < <(jq -r --arg d "$domain" '.requirements[] | select(.domain == $d and .status != "removed") | "\(.id)\t\(.title // "-")"' "$DIGEST_DIR/requirements.json" 2>/dev/null || true)
    done <<< "$domains"

    # Summary block at top
    local grand_merged_pct=0 grand_inprog_pct=0
    if [[ "$grand_total" -gt 0 ]]; then
        grand_merged_pct=$((grand_covered * 100 / grand_total))
        grand_inprog_pct=$((grand_inprogress * 100 / grand_total))
    fi
    local grand_active=$((grand_covered + grand_inprogress))
    local grand_active_pct=$((grand_merged_pct + grand_inprog_pct))

    # Count previously-merged (phase=previous)
    local grand_prev_merged=0
    for domain in "${domain_list[@]}"; do
        grand_prev_merged=$((grand_prev_merged + ${domain_prev_merged[$domain]:-0}))
    done

    echo "<div class=\"coverage-summary cov-summary\" data-total=\"$grand_total\" data-merged=\"$grand_covered\" data-inprog=\"$grand_inprogress\" data-prev-merged=\"$grand_prev_merged\">"
    echo "<strong style=\"font-size:18px\" class=\"cov-num\">$grand_active/$grand_total requirements active ($grand_active_pct%)</strong>"
    echo " — <span class=\"cov-detail\"><span class=\"status-merged\">$grand_covered merged ($grand_merged_pct%)</span> + <span class=\"status-running\">$grand_inprogress in-progress ($grand_inprog_pct%)</span></span>"
    echo "<br><span class=\"coverage-bar\" style=\"width:200px\"><span class=\"coverage-fill\" style=\"width:${grand_merged_pct}%\"></span><span class=\"coverage-fill-inprogress\" style=\"width:${grand_inprog_pct}%\"></span></span>"
    echo "<p style=\"color:#888\" class=\"cov-uncovered\">$((grand_total - grand_active)) uncovered</p>"
    echo "</div>"

    # Per-domain details
    for domain in "${domain_list[@]}"; do
        local dt=${domain_totals[$domain]}
        local dm=${domain_merged[$domain]}
        local di=${domain_inprogress[$domain]}
        local dpm=${domain_prev_merged[$domain]:-0}
        local da=$((dm + di))

        local pct_m=0 pct_i=0
        if [[ "$dt" -gt 0 ]]; then
            pct_m=$((dm * 100 / dt))
            pct_i=$((di * 100 / dt))
        fi
        local pct_a=$((pct_m + pct_i))

        echo "<details class=\"cov-summary\" data-total=\"$dt\" data-merged=\"$dm\" data-inprog=\"$di\" data-prev-merged=\"$dpm\">"
        echo "<summary><strong>$domain</strong> — <span class=\"cov-num\">$da/$dt ($pct_a%)</span> <span class=\"coverage-bar\"><span class=\"coverage-fill\" style=\"width:${pct_m}%\"></span><span class=\"coverage-fill-inprogress\" style=\"width:${pct_i}%\"></span></span></summary>"
        echo "<table><tr><th>REQ</th><th>Title</th><th>Change</th><th>Status</th></tr>"
        echo "${domain_rows[$domain]}"
        echo "</table>"
        echo "</details>"
    done

    # Bottom summary
    echo "<p><strong>Total:</strong> $grand_covered/$grand_total merged ($grand_merged_pct%) | $grand_inprogress in-progress ($grand_inprog_pct%)</p>"
}
