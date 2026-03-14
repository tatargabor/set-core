#!/usr/bin/env bash
# lib/orchestration/digest.sh — Multi-file spec digest: scan, classify, extract requirements
#
# Sourced by bin/wt-orchestrate after planner.sh.
# Provides: cmd_digest(), cmd_coverage(), scan_spec_directory(), build_digest_prompt(),
#           call_digest_api(), write_digest_output(), validate_digest(), stabilize_ids(),
#           check_digest_freshness(), populate_coverage(), check_coverage_gaps(),
#           update_coverage_status(), generate_triage_md(), parse_triage_md(),
#           merge_triage_to_ambiguities(), merge_planner_resolutions()

DIGEST_DIR="wt/orchestration/digest"

# ─── Digest Entry Point ──────────────────────────────────────────────

cmd_digest() {
    local spec_path=""
    local dry_run=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --spec)    spec_path="$2"; shift 2 ;;
            --spec=*)  spec_path="${1#--spec=}"; shift ;;
            --dry-run) dry_run=true; shift ;;
            --help|-h)
                cat <<'USAGE'
Usage: wt-orchestrate digest --spec <path> [--dry-run]

Generate a structured digest from a multi-file specification directory.

Options:
  --spec <path>    Path to spec directory or single file (required)
  --dry-run        Print digest output to stdout without writing files
USAGE
                return 0
                ;;
            *) error "Unknown option: $1"; return 1 ;;
        esac
    done

    if [[ -z "$spec_path" ]]; then
        # Fall back to SPEC_OVERRIDE if set
        if [[ -n "$SPEC_OVERRIDE" ]]; then
            spec_path="$SPEC_OVERRIDE"
        else
            error "Missing required --spec <path>"
            return 1
        fi
    fi

    # Resolve path
    if [[ ! -e "$spec_path" ]]; then
        error "Path not found: $spec_path"
        return 1
    fi

    local abs_spec_path
    abs_spec_path="$(cd "$(dirname "$spec_path")" && pwd)/$(basename "$spec_path")"

    # Scan spec files
    local scan_result
    scan_result=$(scan_spec_directory "$abs_spec_path") || return 1

    local file_count source_hash master_file
    file_count=$(echo "$scan_result" | jq -r '.file_count')
    source_hash=$(echo "$scan_result" | jq -r '.source_hash')
    master_file=$(echo "$scan_result" | jq -r '.master_file // empty')

    info "Scanned $file_count spec file(s), hash=$source_hash"
    if [[ -n "$master_file" ]]; then
        info "Master file: $master_file"
    fi

    emit_event "DIGEST_STARTED" "" "{\"file_count\":$file_count,\"source_hash\":\"$source_hash\"}"

    # Build prompt and call API
    local digest_prompt
    digest_prompt=$(build_digest_prompt "$abs_spec_path" "$scan_result")

    info "Calling Claude for digest generation..."
    log_info "Digest generation started (files=$file_count, hash=$source_hash)"

    # Heartbeat: emit periodic events so sentinel doesn't think we're stuck during long API call
    local _hb_marker
    _hb_marker=$(mktemp)
    (
        local _hb_count=0
        while [[ -f "$_hb_marker" ]]; do
            sleep 60
            [[ -f "$_hb_marker" ]] || break
            _hb_count=$((_hb_count + 1))
            emit_event "DIGEST_HEARTBEAT" "" "{\"minutes\":$_hb_count}" 2>/dev/null || true
        done
    ) &
    local _heartbeat_pid=$!

    local api_response
    api_response=$(call_digest_api "$digest_prompt") || {
        rm -f "$_hb_marker"
        kill "$_heartbeat_pid" 2>/dev/null; wait "$_heartbeat_pid" 2>/dev/null || true
        emit_event "DIGEST_FAILED" "" "{\"reason\":\"api_call_failed\"}"
        error "Digest generation failed"
        return 1
    }
    rm -f "$_hb_marker"
    kill "$_heartbeat_pid" 2>/dev/null; wait "$_heartbeat_pid" 2>/dev/null || true

    emit_event "DIGEST_RESPONSE_RECEIVED" "" "{\"file_count\":$file_count}"

    # Parse structured output from response
    local parsed_output
    parsed_output=$(parse_digest_response "$api_response" "$abs_spec_path" "$scan_result") || {
        emit_event "DIGEST_FAILED" "" "{\"reason\":\"parse_failed\"}"
        error "Failed to parse digest response"
        return 1
    }

    # Stabilize IDs if existing digest present
    if [[ -f "$DIGEST_DIR/requirements.json" ]] && ! $dry_run; then
        parsed_output=$(stabilize_ids "$parsed_output")
    fi

    # Validate
    if ! validate_digest "$parsed_output"; then
        error "Digest validation failed"
        return 1
    fi

    if $dry_run; then
        info "=== DRY RUN — Digest output ==="
        echo "$parsed_output" | jq .
        # Show ambiguities in human-readable format
        local amb_count
        amb_count=$(echo "$parsed_output" | jq '.ambiguities | length')
        if [[ "$amb_count" -gt 0 ]]; then
            echo ""
            info "=== Ambiguities ($amb_count) ==="
            echo "$parsed_output" | jq -r '.ambiguities[] | "  [\(.type)] \(.source):\(.section) — \(.description)"'
        fi
        return 0
    fi

    # Write output atomically
    write_digest_output "$parsed_output" "$abs_spec_path" "$scan_result" || {
        error "Failed to write digest output"
        return 1
    }

    local req_count
    req_count=$(echo "$parsed_output" | jq '.requirements | length')
    local domain_count
    domain_count=$(echo "$parsed_output" | jq '.domains | length')

    success "Digest complete: $req_count requirements across $domain_count domain(s)"
    log_info "Digest complete: files=$file_count, reqs=$req_count, domains=$domain_count, hash=$source_hash"
    emit_event "DIGEST_COMPLETE" "" "{\"file_count\":$file_count,\"req_count\":$req_count,\"domain_count\":$domain_count}"
    generate_report 2>/dev/null || true
}

# ─── Spec Scanning ───────────────────────────────────────────────────

scan_spec_directory() {
    local spec_path="$1"
    local files=()
    local master_file=""

    if [[ -f "$spec_path" ]]; then
        # Single file input
        files=("$spec_path")
        master_file=$(basename "$spec_path")
    elif [[ -d "$spec_path" ]]; then
        # Directory input — find all .md files
        while IFS= read -r f; do
            files+=("$f")
        done < <(find "$spec_path" -name '*.md' -type f | sort)

        if [[ ${#files[@]} -eq 0 ]]; then
            error "No .md files found in $spec_path"
            return 1
        fi

        # Detect master file: v*-*.md or README.md at root
        for f in "${files[@]}"; do
            local rel
            rel="${f#$spec_path/}"
            # Only root-level files
            if [[ "$rel" != */* ]]; then
                local base
                base=$(basename "$f")
                if [[ "$base" =~ ^v[0-9]+-.*\.md$ ]] || [[ "$base" == "README.md" ]]; then
                    master_file="$rel"
                    break
                fi
            fi
        done
    else
        error "Path not found: $spec_path"
        return 1
    fi

    # Compute combined SHA256
    local source_hash
    source_hash=$(printf '%s\n' "${files[@]}" | sort | while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        cat "$f"
    done | sha256sum | cut -d' ' -f1)

    # Build relative file list
    local rel_files=()
    for f in "${files[@]}"; do
        if [[ -d "$spec_path" ]]; then
            rel_files+=("${f#$spec_path/}")
        else
            rel_files+=("$(basename "$f")")
        fi
    done

    # Output JSON
    jq -n \
        --argjson file_count "${#files[@]}" \
        --arg source_hash "$source_hash" \
        --arg master_file "$master_file" \
        --arg spec_base_dir "$spec_path" \
        --argjson files "$(printf '%s\n' "${rel_files[@]}" | jq -R . | jq -s .)" \
        '{
            file_count: $file_count,
            source_hash: $source_hash,
            master_file: (if $master_file != "" then $master_file else null end),
            spec_base_dir: $spec_base_dir,
            files: $files
        }'
}

# ─── Prompt Construction ─────────────────────────────────────────────

build_digest_prompt() {
    local spec_path="$1"
    local scan_result="$2"

    local master_file
    master_file=$(echo "$scan_result" | jq -r '.master_file // empty')

    # Concatenate all spec files with headers
    local spec_content=""
    local files
    files=$(echo "$scan_result" | jq -r '.files[]')

    # If master file exists, put it first
    if [[ -n "$master_file" ]]; then
        local master_path
        if [[ -f "$spec_path" ]]; then
            master_path="$spec_path"
        else
            master_path="$spec_path/$master_file"
        fi
        if [[ -f "$master_path" ]]; then
            spec_content+="=== FILE: $master_file ===
$(cat "$master_path")

"
        fi
    fi

    # Add remaining files
    while IFS= read -r rel_file; do
        [[ -z "$rel_file" ]] && continue
        [[ "$rel_file" == "$master_file" ]] && continue  # already added
        local full_path
        if [[ -f "$spec_path" ]]; then
            full_path="$spec_path"
        else
            full_path="$spec_path/$rel_file"
        fi
        if [[ -f "$full_path" ]]; then
            spec_content+="=== FILE: $rel_file ===
$(cat "$full_path")

"
        fi
    done <<< "$files"

    cat <<DIGEST_PROMPT_EOF
You are a technical analyst processing a product specification into a structured digest for an orchestration system.

## Specification Files

$spec_content

## Instructions

Analyze ALL specification files above and produce a structured digest. Follow these rules precisely:

### 1. File Classification
Classify each file as one of:
- **convention**: Project-wide rules that apply to every change (i18n routing, SEO patterns, design system tokens, naming conventions)
- **feature**: Behavioral requirements for specific functionality (cart operations, user registration, admin CRUD)
- **data**: Entity definitions, catalogs, seed data with attributes (product lists, user roles, categories). Individual data entries are NOT requirements.
- **execution**: Implementation plans, change scoping, dependency graphs, verification checklists

Heuristic:
- Files defining rules/patterns that span multiple features → convention
- Files describing what a specific feature does (behaviors, user stories, flows) → feature
- Files listing entities, items, or seed data with attributes → data
- Files describing implementation order, change scope, or acceptance checklists → execution

### 2. Requirement Extraction
From files classified as **feature**, extract discrete, independently testable requirements.

**Granularity**: One requirement = one independently testable behavior. If it needs its own test case, it is a separate requirement. "Cart supports coupons" is too broad; "ELSO10 coupon gives 10% on first order only" is the right granularity.

**REQUIREMENT GRANULARITY RULES:**
- Each requirement MUST describe exactly ONE testable behavior
- CRUD operations on an entity = minimum 4 separate requirements (create, read, update, delete)
- If a spec section lists multiple distinct user actions, create one REQ per action
- Edge cases and error handling explicitly mentioned in spec = separate requirements
- Compound descriptions like "Users can X and Y" = TWO requirements, not one
- A requirement is too coarse if you cannot write a single test for it without covering multiple independent behaviors

**ID format**: REQ-{DOMAIN_SHORT}-{NNN} (e.g., REQ-CART-001, REQ-SUB-003)

Each requirement must have: id, title, source (file path), source_section (heading), domain, brief (1-2 sentence summary).

**Cross-cutting requirements**: Requirements that span multiple features (i18n integration, responsive layout, auth checks) get \`cross_cutting: true\` and \`affects_domains: ["domain1", "domain2"]\`.

### 3. De-duplication
If a master file contains a verification checklist or acceptance criteria that restates requirements from feature files, do NOT create duplicate REQ-* IDs. Each unique behavior gets exactly one ID, sourced from the most detailed description.

### 4. Embedded Behavioral Rules
Data files (catalogs, seed data) may contain embedded behavioral rules (business logic, calculations, validation rules, state machines). Extract these as separate REQ-* IDs even though the file is classified as data. Individual data entries (each product, each item) are NOT requirements.

### 5. Convention Extraction
From files classified as **convention** (and convention-like sections in mixed files), extract project-wide rules into a conventions structure.

### 6. Data Definitions
From files classified as **data**, produce a summary of entities, their attributes, and relationships.

### 7. Domain Grouping
Group requirements into domains based on directory structure or topic similarity. Each domain gets a markdown summary with: overview, list of features, cross-references to other domains, requirement count.

### 8. Dependencies
Identify dependencies between requirements across files. Include IMPLICIT dependencies: cases where implementing feature A requires data or state from feature B, even if there is no explicit text reference.

### 9. Ambiguity Detection
Report:
- **underspecified**: behavior described but details missing
- **contradictory**: two files describe the same thing differently
- **missing_reference**: one file references a behavior/template/entity in another file that doesn't exist
- **implicit_assumption**: behavior depends on an undeclared dependency

### 10. Execution Hints
Files classified as **execution** → store as optional execution_hints (suggested change boundaries, dependency ordering).

## CRITICAL: Output Size Limit

Your ENTIRE JSON response MUST fit in a SINGLE message — you will NOT get a second turn.
Strict limits:
- MAX 50 requirements total. If your initial count exceeds 50, merge aggressively:
  group related CRUD operations, combine similar UI behaviors, roll detailed sub-features into parent features.
- Requirement briefs: ONE short sentence only
- Domain summaries: 1-2 sentences max
- MAX 10 ambiguities (only critical ones that block implementation)
- MAX 30 dependencies (only hard functional dependencies, skip informational references)
- Omit execution_hints entirely (use empty object: {})
- Do NOT split your response across messages. Everything in ONE JSON block.

## Output Format

Respond with valid JSON only (no markdown fences, no commentary):

{
  "file_classifications": {
    "path/to/file.md": "convention|feature|data|execution"
  },
  "conventions": {
    "categories": [
      {
        "name": "Category Name",
        "rules": ["Rule 1", "Rule 2"]
      }
    ]
  },
  "data_definitions": "Markdown string summarizing entities, catalogs, and data models",
  "requirements": [
    {
      "id": "REQ-DOMAIN-NNN",
      "title": "Short title",
      "source": "path/to/file.md",
      "source_section": "Section heading",
      "domain": "domain-name",
      "brief": "1-2 sentence description of the testable behavior"
    }
  ],
  "domains": [
    {
      "name": "domain-name",
      "summary": "Markdown overview of the domain"
    }
  ],
  "dependencies": [
    {
      "from": "REQ-XXX-NNN",
      "to": "REQ-YYY-NNN",
      "type": "depends_on|references"
    }
  ],
  "ambiguities": [
    {
      "id": "AMB-NNN",
      "type": "underspecified|contradictory|missing_reference|implicit_assumption",
      "source": "path/to/file.md",
      "section": "Section heading",
      "description": "What is unclear or conflicting",
      "affects_requirements": ["REQ-XXX-NNN"]
    }
  ],
  "execution_hints": {}
}
DIGEST_PROMPT_EOF
}

# ─── API Call ────────────────────────────────────────────────────────

call_digest_api() {
    local prompt="$1"
    local output
    output=$(export RUN_CLAUDE_NO_MCP=1 RUN_CLAUDE_TIMEOUT=600; echo "$prompt" | run_claude --model "$(model_id opus)" --max-turns 1) || {
        log_error "Digest API call failed"
        return 1
    }
    echo "$output"
}

# ─── Response Parsing ────────────────────────────────────────────────

parse_digest_response() {
    local raw_response="$1"
    local spec_path="$2"
    local scan_result="$3"

    # Save raw response for debugging
    local response_file=".claude/digest-last-response.txt"
    mkdir -p .claude
    printf '%s' "$raw_response" > "$response_file" 2>/dev/null

    # Extract JSON from response
    python3 -c "
import json, sys, re

raw = sys.stdin.read()

# Strategy 1: direct parse
try:
    data = json.loads(raw)
    if 'requirements' in data:
        print(json.dumps(data))
        sys.exit(0)
except Exception:
    pass

# Strategy 2: strip markdown fences
stripped = re.sub(r'\`\`\`(?:json|JSON)?\s*\n?', '', raw).strip()
try:
    data = json.loads(stripped)
    if 'requirements' in data:
        print(json.dumps(data))
        sys.exit(0)
except Exception:
    pass

# Strategy 3: find JSON by braces
first_brace = raw.find('{')
if first_brace >= 0:
    for j in range(len(raw) - 1, first_brace, -1):
        if raw[j] == '}':
            try:
                data = json.loads(raw[first_brace:j+1])
                if 'requirements' in data:
                    print(json.dumps(data))
                    sys.exit(0)
            except Exception:
                continue

print('ERROR: Could not parse digest JSON', file=sys.stderr)
sys.exit(1)
" <<< "$raw_response"
}

# ─── Output Writing ──────────────────────────────────────────────────

write_digest_output() {
    local parsed="$1"
    local spec_path="$2"
    local scan_result="$3"

    # Atomic write: temp dir first, move on success
    local tmp_dir
    tmp_dir=$(mktemp -d)
    trap "rm -rf '$tmp_dir'" RETURN

    local source_hash file_count
    source_hash=$(echo "$scan_result" | jq -r '.source_hash')
    file_count=$(echo "$scan_result" | jq -r '.file_count')

    # index.json
    jq -n \
        --arg spec_base_dir "$spec_path" \
        --arg source_hash "$source_hash" \
        --argjson file_count "$file_count" \
        --arg timestamp "$(date -Iseconds)" \
        --argjson files "$(echo "$scan_result" | jq '.files')" \
        --argjson classifications "$(echo "$parsed" | jq '.file_classifications // {}')" \
        --argjson execution_hints "$(echo "$parsed" | jq '.execution_hints // {}')" \
        '{
            spec_base_dir: $spec_base_dir,
            source_hash: $source_hash,
            file_count: $file_count,
            timestamp: $timestamp,
            files: $files,
            file_classifications: $classifications,
            execution_hints: $execution_hints
        }' > "$tmp_dir/index.json"

    # conventions.json
    echo "$parsed" | jq '.conventions // {"categories": []}' > "$tmp_dir/conventions.json"

    # data-definitions.md
    local data_defs
    data_defs=$(echo "$parsed" | jq -r '.data_definitions // "No data definitions found."')
    echo "$data_defs" > "$tmp_dir/data-definitions.md"

    # requirements.json
    jq -n --argjson reqs "$(echo "$parsed" | jq '.requirements // []')" \
        '{requirements: $reqs}' > "$tmp_dir/requirements.json"

    # dependencies.json
    jq -n --argjson deps "$(echo "$parsed" | jq '.dependencies // []')" \
        '{dependencies: $deps}' > "$tmp_dir/dependencies.json"

    # ambiguities.json
    jq -n --argjson ambs "$(echo "$parsed" | jq '.ambiguities // []')" \
        '{ambiguities: $ambs}' > "$tmp_dir/ambiguities.json"

    # triage.md (only when ambiguities exist)
    local amb_count
    amb_count=$(echo "$parsed" | jq '.ambiguities // [] | length')
    if [[ "$amb_count" -gt 0 ]]; then
        local existing_triage=""
        if [[ -f "$DIGEST_DIR/triage.md" ]]; then
            existing_triage="$DIGEST_DIR/triage.md"
        fi
        generate_triage_md "$tmp_dir/ambiguities.json" "$tmp_dir/triage.md" "$existing_triage"
    fi

    # coverage.json (empty skeleton — populated after plan)
    if [[ -f "$DIGEST_DIR/coverage.json" ]]; then
        # Preserve existing coverage on re-digest
        cp "$DIGEST_DIR/coverage.json" "$tmp_dir/coverage.json"
    else
        echo '{"coverage": {}, "uncovered": []}' > "$tmp_dir/coverage.json"
    fi

    # domains/*.md
    mkdir -p "$tmp_dir/domains"
    local domain_count
    domain_count=$(echo "$parsed" | jq '.domains | length')
    for ((i=0; i<domain_count; i++)); do
        local domain_name domain_summary
        domain_name=$(echo "$parsed" | jq -r ".domains[$i].name")
        domain_summary=$(echo "$parsed" | jq -r ".domains[$i].summary")
        echo "$domain_summary" > "$tmp_dir/domains/${domain_name}.md"
    done

    # Move to final location
    mkdir -p "$(dirname "$DIGEST_DIR")"
    if [[ -d "$DIGEST_DIR" ]]; then
        # Preserve coverage.json from old digest if not already copied
        if [[ -f "$DIGEST_DIR/coverage.json" && ! -f "$tmp_dir/coverage.json" ]]; then
            cp "$DIGEST_DIR/coverage.json" "$tmp_dir/coverage.json"
        fi
        rm -rf "$DIGEST_DIR"
    fi
    mv "$tmp_dir" "$DIGEST_DIR"
    trap - RETURN

    log_info "Digest output written to $DIGEST_DIR"
}

# ─── Triage Template ─────────────────────────────────────────────────

# Generate triage.md from ambiguities.json for human review.
# If triage.md already exists, preserves existing decisions for ambiguities
# that still exist, marks removed ones with [REMOVED], appends new ones.
generate_triage_md() {
    local amb_file="$1"
    local output_file="$2"
    local existing_triage="${3:-}"

    local amb_count
    amb_count=$(jq '.ambiguities | length' "$amb_file" 2>/dev/null || echo 0)
    if [[ "$amb_count" -eq 0 ]]; then
        return 0
    fi

    # Parse existing triage decisions if file exists
    local existing_decisions='{}'
    if [[ -n "$existing_triage" && -f "$existing_triage" ]]; then
        existing_decisions=$(parse_triage_md "$existing_triage")
    fi

    # Collect current AMB IDs
    local current_ids
    current_ids=$(jq -r '.ambiguities[].id' "$amb_file" 2>/dev/null || true)

    # Build triage.md
    {
        cat <<'TRIAGE_HEADER'
# Ambiguity Triage
<!-- Generated by wt-orchestrate digest — edit decisions, then re-run plan -->

## Instructions
For each ambiguity, set the **Decision** to one of:
- `fix` — spec needs correction before planning (blocks pipeline until fixed and re-digested)
- `defer` — planner will decide during change design
- `ignore` — not relevant or out of scope

---

TRIAGE_HEADER

        # Render current ambiguities
        jq -r '.ambiguities[] | @json' "$amb_file" | while IFS= read -r amb_json; do
            local amb_id amb_type amb_source amb_section amb_desc amb_affects
            amb_id=$(echo "$amb_json" | jq -r '.id')
            amb_type=$(echo "$amb_json" | jq -r '.type')
            amb_source=$(echo "$amb_json" | jq -r '.source // "unknown"')
            amb_section=$(echo "$amb_json" | jq -r '.section // "unknown"')
            amb_desc=$(echo "$amb_json" | jq -r '.description')
            amb_affects=$(echo "$amb_json" | jq -r '.affects_requirements // [] | join(", ")')

            # Check for existing decision
            local prev_decision="" prev_note=""
            prev_decision=$(echo "$existing_decisions" | jq -r --arg id "$amb_id" '.[$id].decision // ""')
            prev_note=$(echo "$existing_decisions" | jq -r --arg id "$amb_id" '.[$id].note // ""')

            echo "### $amb_id [$amb_type]"
            echo "**Source:** $amb_source § $amb_section"
            echo "**Description:** $amb_desc"
            if [[ -n "$amb_affects" ]]; then
                echo "**Affects:** $amb_affects"
            fi
            echo ""
            echo "**Decision:** $prev_decision"
            echo "**Note:** $prev_note"
            echo ""
            echo "---"
            echo ""
        done

        # Append removed entries (were in old triage but not in current ambiguities)
        if [[ -n "$existing_triage" && -f "$existing_triage" ]]; then
            local old_ids
            old_ids=$(echo "$existing_decisions" | jq -r 'keys[]' 2>/dev/null || true)
            while IFS= read -r old_id; do
                [[ -z "$old_id" ]] && continue
                if ! echo "$current_ids" | grep -qxF "$old_id"; then
                    local old_decision old_note
                    old_decision=$(echo "$existing_decisions" | jq -r --arg id "$old_id" '.[$id].decision // ""')
                    old_note=$(echo "$existing_decisions" | jq -r --arg id "$old_id" '.[$id].note // ""')
                    echo "### $old_id [REMOVED]"
                    echo "**Decision:** $old_decision"
                    echo "**Note:** $old_note"
                    echo ""
                    echo "---"
                    echo ""
                fi
            done <<< "$old_ids"
        fi
    } > "$output_file"
}

# Parse triage.md — extract decisions and notes per AMB ID.
# Returns JSON object: {"AMB-001": {"decision": "defer", "note": "..."}, ...}
# Invalid decisions (not fix/defer/ignore) are treated as blank (untriaged).
# [REMOVED] entries are skipped.
parse_triage_md() {
    local triage_file="$1"

    if [[ ! -f "$triage_file" ]]; then
        echo '{}'
        return 0
    fi

    python3 -c "
import re, json, sys

content = open(sys.argv[1]).read()
result = {}

# Split by ### headers
sections = re.split(r'^### ', content, flags=re.MULTILINE)
for section in sections:
    if not section.strip():
        continue

    # Parse AMB ID and check for [REMOVED]
    header_match = re.match(r'(AMB-\d+)\s*\[([^\]]+)\]', section)
    if not header_match:
        continue

    amb_id = header_match.group(1)
    tag = header_match.group(2)

    if tag == 'REMOVED':
        continue

    # Extract decision
    decision_match = re.search(r'\*\*Decision:\*\*\s*(.*?)$', section, re.MULTILINE)
    decision = decision_match.group(1).strip() if decision_match else ''

    # Validate decision
    if decision not in ('fix', 'defer', 'ignore'):
        decision = ''

    # Extract note
    note_match = re.search(r'\*\*Note:\*\*\s*(.*?)$', section, re.MULTILINE)
    note = note_match.group(1).strip() if note_match else ''

    result[amb_id] = {'decision': decision, 'note': note}

print(json.dumps(result))
" "$triage_file"
}

# Merge triage decisions into ambiguities.json — adds resolution, resolution_note, resolved_by fields.
merge_triage_to_ambiguities() {
    local amb_file="$1"
    local triage_decisions="$2"  # JSON from parse_triage_md
    local resolved_by="${3:-triage}"

    local tmp
    tmp=$(mktemp)

    jq --argjson decisions "$triage_decisions" --arg by "$resolved_by" '
        .ambiguities = [.ambiguities[] | . as $amb |
            if $decisions[$amb.id] and ($decisions[$amb.id].decision | length > 0) then
                .resolution = (if $decisions[$amb.id].decision == "fix" then "fixed"
                    elif $decisions[$amb.id].decision == "defer" then "deferred"
                    elif $decisions[$amb.id].decision == "ignore" then "ignored"
                    else $decisions[$amb.id].decision end) |
                .resolution_note = $decisions[$amb.id].note |
                .resolved_by = $by
            else . end
        ]
    ' "$amb_file" > "$tmp" && mv "$tmp" "$amb_file"
}

# Merge planner resolved_ambiguities back into ambiguities.json
merge_planner_resolutions() {
    local amb_file="$1"
    local plan_file="$2"

    if [[ ! -f "$amb_file" || ! -f "$plan_file" ]]; then
        return 0
    fi

    # Collect all resolved_ambiguities from plan changes
    local resolutions
    resolutions=$(jq '[.changes[]? | .resolved_ambiguities[]? // empty] | if length == 0 then null else . end' "$plan_file" 2>/dev/null || echo "null")

    if [[ "$resolutions" == "null" ]]; then
        return 0
    fi

    local tmp
    tmp=$(mktemp)

    jq --argjson resolutions "$resolutions" '
        .ambiguities = [.ambiguities[] | . as $amb |
            ($resolutions | map(select(.id == $amb.id)) | first // null) as $res |
            if $res then
                .resolution = "planner-resolved" |
                .resolution_note = ($res.resolution_note // "") |
                .resolved_by = "planner"
            else . end
        ]
    ' "$amb_file" > "$tmp" && mv "$tmp" "$amb_file"
}

# ─── Validation ──────────────────────────────────────────────────────

validate_digest() {
    local parsed="$1"
    local errors=0

    # Check requirements have valid IDs
    local bad_ids
    bad_ids=$(echo "$parsed" | jq -r '.requirements[]? | select(.id | test("^REQ-[A-Z0-9]+-[0-9]+$") | not) | .id' 2>/dev/null || true)
    if [[ -n "$bad_ids" ]]; then
        warn "Invalid requirement IDs (must match REQ-{DOMAIN}-{NNN}): $bad_ids"
        errors=$((errors + 1))
    fi

    # Check for duplicate IDs
    local dup_ids
    dup_ids=$(echo "$parsed" | jq -r '[.requirements[]?.id] | group_by(.) | map(select(length > 1) | .[0]) | .[]' 2>/dev/null || true)
    if [[ -n "$dup_ids" ]]; then
        warn "Duplicate requirement IDs: $dup_ids"
        errors=$((errors + 1))
    fi

    # Check conventions.json is valid
    if ! echo "$parsed" | jq -e '.conventions' &>/dev/null; then
        warn "Missing or invalid conventions"
        errors=$((errors + 1))
    fi

    # Check domains exist for each domain referenced in requirements
    local req_domains
    req_domains=$(echo "$parsed" | jq -r '[.requirements[]?.domain] | unique | .[]' 2>/dev/null || true)
    local digest_domains
    digest_domains=$(echo "$parsed" | jq -r '[.domains[]?.name] | .[]' 2>/dev/null || true)
    if [[ -n "$req_domains" ]]; then
        while IFS= read -r rd; do
            [[ -z "$rd" ]] && continue
            if ! echo "$digest_domains" | grep -qxF "$rd"; then
                warn "Domain '$rd' referenced in requirements but no domain summary exists"
                errors=$((errors + 1))
            fi
        done <<< "$req_domains"
    fi

    # Check dependencies reference valid requirement IDs
    local all_req_ids
    all_req_ids=$(echo "$parsed" | jq -r '[.requirements[]?.id] | .[]' 2>/dev/null || true)
    local dep_refs
    dep_refs=$(echo "$parsed" | jq -r '.dependencies[]? | .from, .to' 2>/dev/null || true)
    if [[ -n "$dep_refs" ]]; then
        while IFS= read -r ref; do
            [[ -z "$ref" ]] && continue
            if ! echo "$all_req_ids" | grep -qxF "$ref"; then
                warn "Dependency references non-existent requirement: $ref"
                errors=$((errors + 1))
            fi
        done <<< "$dep_refs"
    fi

    # Check cross-cutting requirements have affects_domains
    local cc_missing
    cc_missing=$(echo "$parsed" | jq -r '.requirements[]? | select(.cross_cutting == true and (.affects_domains | length == 0 or . == null)) | .id' 2>/dev/null || true)
    if [[ -n "$cc_missing" ]]; then
        warn "Cross-cutting requirements missing affects_domains: $cc_missing"
        errors=$((errors + 1))
    fi

    return $errors
}

# ─── ID Stabilization ───────────────────────────────────────────────

stabilize_ids() {
    local new_parsed="$1"

    if [[ ! -f "$DIGEST_DIR/requirements.json" ]]; then
        echo "$new_parsed"
        return 0
    fi

    python3 -c "
import json, sys

new_data = json.loads(sys.stdin.read())
with open('$DIGEST_DIR/requirements.json') as f:
    old_data = json.load(f)

old_reqs = {(r['source'], r.get('source_section', '')): r for r in old_data.get('requirements', [])}
old_by_id = {r['id']: r for r in old_data.get('requirements', [])}

# Track used IDs
used_ids = set()
stabilized = []

# Match new requirements against existing by source + source_section
for req in new_data.get('requirements', []):
    key = (req['source'], req.get('source_section', ''))
    if key in old_reqs:
        old_req = old_reqs[key]
        req['id'] = old_req['id']
        used_ids.add(req['id'])
    stabilized.append(req)

# Assign new IDs for unmatched requirements
domain_counters = {}
for req in stabilized:
    if req['id'] not in used_ids:
        used_ids.add(req['id'])
    # Track highest ID per domain
    parts = req['id'].split('-')
    if len(parts) >= 3:
        domain = parts[1]
        num = int(parts[2])
        domain_counters[domain] = max(domain_counters.get(domain, 0), num)

# Mark removed requirements
for old_req in old_data.get('requirements', []):
    if old_req['id'] not in used_ids:
        removed = dict(old_req)
        removed['status'] = 'removed'
        stabilized.append(removed)

new_data['requirements'] = stabilized
print(json.dumps(new_data))
" <<< "$new_parsed"
}

# ─── Freshness Check ────────────────────────────────────────────────

check_digest_freshness() {
    local spec_path="$1"

    if [[ ! -f "$DIGEST_DIR/index.json" ]]; then
        echo "missing"
        return 0
    fi

    local stored_hash
    stored_hash=$(jq -r '.source_hash' "$DIGEST_DIR/index.json")

    local current_scan
    current_scan=$(scan_spec_directory "$spec_path") || {
        echo "error"
        return 1
    }
    local current_hash
    current_hash=$(echo "$current_scan" | jq -r '.source_hash')

    if [[ "$stored_hash" == "$current_hash" ]]; then
        echo "fresh"
    else
        echo "stale"
    fi
}

# ─── Coverage Population ────────────────────────────────────────────

populate_coverage() {
    local plan_file="$1"

    if [[ ! -f "$DIGEST_DIR/requirements.json" ]]; then
        log_warn "populate_coverage: no requirements.json — skipping"
        return 0
    fi

    local coverage='{}'

    # Iterate changes in plan, map requirements
    local changes
    changes=$(jq -c '.changes[]' "$plan_file" 2>/dev/null || true)

    while IFS= read -r change_json; do
        [[ -z "$change_json" ]] && continue
        local change_name
        change_name=$(echo "$change_json" | jq -r '.name')

        # Primary owned requirements
        local reqs
        reqs=$(echo "$change_json" | jq -r '.requirements[]? // empty' 2>/dev/null || true)
        while IFS= read -r req_id; do
            [[ -z "$req_id" ]] && continue
            coverage=$(echo "$coverage" | jq --arg id "$req_id" --arg change "$change_name" \
                '.[$id] = {"change": $change, "status": "planned"}')
        done <<< "$reqs"

        # Cross-cutting (also_affects_reqs)
        local also_affects
        also_affects=$(echo "$change_json" | jq -r '.also_affects_reqs[]? // empty' 2>/dev/null || true)
        while IFS= read -r req_id; do
            [[ -z "$req_id" ]] && continue
            # Add to also_affects list if primary entry already exists
            coverage=$(echo "$coverage" | jq --arg id "$req_id" --arg change "$change_name" \
                'if .[$id] then .[$id].also_affects = ((.[$id].also_affects // []) + [$change] | unique) else . end')
        done <<< "$also_affects"
    done <<< "$changes"

    # Track cross-cutting REQs that are in also_affects but have no primary owner
    local also_affects_only='{}'
    while IFS= read -r change_json; do
        [[ -z "$change_json" ]] && continue
        local _aa_change_name
        _aa_change_name=$(echo "$change_json" | jq -r '.name')
        local _aa_reqs
        _aa_reqs=$(echo "$change_json" | jq -r '.also_affects_reqs[]? // empty' 2>/dev/null || true)
        while IFS= read -r _aa_id; do
            [[ -z "$_aa_id" ]] && continue
            # If not in primary coverage, track which changes reference it
            local _has_primary
            _has_primary=$(echo "$coverage" | jq --arg id "$_aa_id" 'has($id)')
            if [[ "$_has_primary" == "false" ]]; then
                also_affects_only=$(echo "$also_affects_only" | jq --arg id "$_aa_id" --arg change "$_aa_change_name" \
                    '.[$id] = ((.[$id] // []) + [$change] | unique)')
            fi
        done <<< "$_aa_reqs"
    done <<< "$changes"

    # Restore previously-merged requirements from persistent history
    local merged_history="$DIGEST_DIR/coverage-merged.json"
    if [[ -f "$merged_history" ]]; then
        local prev_ids
        prev_ids=$(jq -r 'keys[]' "$merged_history" 2>/dev/null || true)
        while IFS= read -r prev_id; do
            [[ -z "$prev_id" ]] && continue
            local already_covered
            already_covered=$(echo "$coverage" | jq --arg id "$prev_id" 'has($id)')
            if [[ "$already_covered" == "false" ]]; then
                local prev_entry
                prev_entry=$(jq --arg id "$prev_id" '.[$id]' "$merged_history")
                coverage=$(echo "$coverage" | jq --arg id "$prev_id" --argjson entry "$prev_entry" '.[$id] = ($entry + {phase: "previous"})')
            fi
        done <<< "$prev_ids"
        log_info "Restored $(echo "$prev_ids" | grep -c . || true) previously-merged requirements from history"
    fi

    # Write coverage.json
    local uncovered
    uncovered=$(check_coverage_gaps_internal "$coverage")

    jq -n --argjson cov "$coverage" --argjson unc "$uncovered" \
        '{coverage: $cov, uncovered: $unc}' > "$DIGEST_DIR/coverage.json"

    local covered_count
    covered_count=$(echo "$coverage" | jq 'length')
    log_info "Coverage populated: $covered_count requirements mapped"

    # Warn or error about uncovered
    local unc_count
    unc_count=$(echo "$uncovered" | jq 'length')

    # Add notes about also_affects-only REQs
    local aa_only_count
    aa_only_count=$(echo "$also_affects_only" | jq 'length')
    if [[ "$aa_only_count" -gt 0 ]]; then
        local aa_ids
        aa_ids=$(echo "$also_affects_only" | jq -r 'keys[]')
        while IFS= read -r aa_id; do
            [[ -z "$aa_id" ]] && continue
            local aa_changes
            aa_changes=$(echo "$also_affects_only" | jq -r --arg id "$aa_id" '.[$id] | join(", ")')
            warn "Cross-cutting $aa_id has no primary owner (referenced by also_affects in: $aa_changes)"
        done <<< "$aa_ids"
    fi

    if [[ "$unc_count" -gt 0 ]]; then
        local unc_list
        unc_list=$(echo "$uncovered" | jq -r '.[]' | tr '\n' ', ')

        if [[ "${REQUIRE_FULL_COVERAGE:-false}" == "true" ]]; then
            error "Coverage incomplete: $unc_count requirement(s) not assigned: $unc_list"
            error "Re-run plan or set require_full_coverage: false to proceed"
            return 1
        else
            warn "Warning: $unc_count uncovered requirement(s): $unc_list"
        fi
    fi
}

check_coverage_gaps() {
    if [[ ! -f "$DIGEST_DIR/coverage.json" || ! -f "$DIGEST_DIR/requirements.json" ]]; then
        return 0
    fi

    local coverage
    coverage=$(jq '.coverage' "$DIGEST_DIR/coverage.json")
    local uncovered
    uncovered=$(check_coverage_gaps_internal "$coverage")

    local unc_count
    unc_count=$(echo "$uncovered" | jq 'length')
    if [[ "$unc_count" -gt 0 ]]; then
        # Update uncovered list in coverage.json
        local tmp
        tmp=$(mktemp)
        jq --argjson unc "$uncovered" '.uncovered = $unc' "$DIGEST_DIR/coverage.json" > "$tmp" && mv "$tmp" "$DIGEST_DIR/coverage.json"
        warn "$unc_count uncovered requirement(s)"
    fi
}

# Internal: compute uncovered requirement IDs
check_coverage_gaps_internal() {
    local coverage="$1"

    if [[ ! -f "$DIGEST_DIR/requirements.json" ]]; then
        echo '[]'
        return 0
    fi

    local all_ids
    all_ids=$(jq -r '.requirements[] | select(.status != "removed") | .id' "$DIGEST_DIR/requirements.json" 2>/dev/null || true)
    local covered_ids
    covered_ids=$(echo "$coverage" | jq -r 'keys[]' 2>/dev/null || true)

    local uncovered=()
    while IFS= read -r id; do
        [[ -z "$id" ]] && continue
        if ! echo "$covered_ids" | grep -qxF "$id"; then
            uncovered+=("$id")
        fi
    done <<< "$all_ids"

    if [[ ${#uncovered[@]} -eq 0 ]]; then
        echo '[]'
    else
        printf '%s\n' "${uncovered[@]}" | jq -R . | jq -s . 2>/dev/null || echo '[]'
    fi
}

# ─── Coverage Status Updates ────────────────────────────────────────

update_coverage_status() {
    local change_name="$1"
    local new_status="$2"

    if [[ ! -f "$DIGEST_DIR/coverage.json" ]]; then
        return 0
    fi

    local tmp
    tmp=$(mktemp)
    jq --arg change "$change_name" --arg status "$new_status" \
        '.coverage = (.coverage | to_entries | map(
            if .value.change == $change then .value.status = $status else . end
        ) | from_entries)' "$DIGEST_DIR/coverage.json" > "$tmp" && mv "$tmp" "$DIGEST_DIR/coverage.json"

    # Persist merged requirements to history (survives replan)
    if [[ "$new_status" == "merged" ]]; then
        local merged_history="$DIGEST_DIR/coverage-merged.json"
        local merged_entries
        merged_entries=$(jq --arg change "$change_name" \
            '[.coverage | to_entries[] | select(.value.change == $change)] | from_entries' \
            "$DIGEST_DIR/coverage.json" 2>/dev/null || echo '{}')
        if [[ -f "$merged_history" ]]; then
            local merged_tmp
            merged_tmp=$(mktemp)
            jq --argjson new "$merged_entries" '. * $new' "$merged_history" > "$merged_tmp" && mv "$merged_tmp" "$merged_history"
        else
            echo "$merged_entries" > "$merged_history"
        fi
    fi

    log_info "Coverage status updated: $change_name → $new_status"
}

# ─── Final Coverage Check ────────────────────────────────────────────

# Cross-reference coverage.json with orchestration-state.json to categorize
# each requirement as merged/running/planned/uncovered/failed/blocked.
# Emits COVERAGE_GAP event if gaps exist. Returns formatted summary string.
# Returns empty if no digest data.
final_coverage_check() {
    if [[ ! -f "$DIGEST_DIR/coverage.json" || ! -f "$DIGEST_DIR/requirements.json" ]]; then
        return 0
    fi

    if [[ ! -f "$STATE_FILENAME" ]]; then
        return 0
    fi

    local merged=0 running=0 planned=0 uncovered_count=0 failed=0 blocked=0

    local all_req_ids
    all_req_ids=$(jq -r '.requirements[] | select(.status != "removed") | .id' "$DIGEST_DIR/requirements.json" 2>/dev/null || true)

    local total=0
    while IFS= read -r req_id; do
        [[ -z "$req_id" ]] && continue
        total=$((total + 1))

        # Get coverage entry for this req
        local cov_change cov_status
        cov_change=$(jq -r --arg id "$req_id" '.coverage[$id].change // empty' "$DIGEST_DIR/coverage.json" 2>/dev/null || true)
        cov_status=$(jq -r --arg id "$req_id" '.coverage[$id].status // empty' "$DIGEST_DIR/coverage.json" 2>/dev/null || true)

        if [[ -z "$cov_change" ]]; then
            uncovered_count=$((uncovered_count + 1))
            continue
        fi

        # Cross-reference with state to get effective status
        local change_status
        change_status=$(jq -r --arg n "$cov_change" '.changes[] | select(.name == $n) | .status // empty' "$STATE_FILENAME" 2>/dev/null || true)

        case "$change_status" in
            merged|done)
                merged=$((merged + 1))
                ;;
            failed)
                failed=$((failed + 1))
                ;;
            merge-blocked)
                blocked=$((blocked + 1))
                ;;
            running|verifying|stalled)
                running=$((running + 1))
                ;;
            *)
                planned=$((planned + 1))
                ;;
        esac
    done <<< "$all_req_ids"

    # Emit COVERAGE_GAP event if any gaps
    local gap_count=$((uncovered_count + failed + blocked))
    if [[ "$gap_count" -gt 0 ]]; then
        emit_event "COVERAGE_GAP" "" \
            "{\"uncovered\":$uncovered_count,\"failed\":$failed,\"blocked\":$blocked,\"merged\":$merged,\"total\":$total}"
    fi

    # Build and output summary
    local summary
    summary="Coverage: $merged merged, $running running, $planned planned, $uncovered_count uncovered, $failed failed, $blocked blocked (total: $total)"

    if [[ "$gap_count" -gt 0 ]]; then
        log_warn "Final coverage: $summary"
    else
        log_info "Final coverage: $summary"
    fi

    echo "$summary"
}

# One-line coverage summary for email/notifications.
build_coverage_summary() {
    final_coverage_check
}

# ─── Coverage Report ────────────────────────────────────────────────

cmd_coverage() {
    if [[ ! -d "$DIGEST_DIR" ]]; then
        info "No digest found. Run \`wt-orchestrate digest --spec <path>\` first."
        return 0
    fi

    if [[ ! -f "$DIGEST_DIR/requirements.json" ]]; then
        info "No requirements.json found in digest."
        return 0
    fi

    local req_count
    req_count=$(jq '.requirements | length' "$DIGEST_DIR/requirements.json")

    if [[ ! -f "$DIGEST_DIR/coverage.json" ]] || \
       [[ "$(jq '.coverage | length' "$DIGEST_DIR/coverage.json")" -eq 0 ]]; then
        info "Requirements: $req_count total"
        info "No plan generated yet. All requirements uncovered."
        return 0
    fi

    echo ""
    info "═══ Coverage Report ═══"
    echo ""

    # Per-domain breakdown
    local domains
    domains=$(jq -r '[.requirements[] | select(.status != "removed") | .domain] | unique | .[]' "$DIGEST_DIR/requirements.json" 2>/dev/null || true)

    while IFS= read -r domain; do
        [[ -z "$domain" ]] && continue
        local domain_reqs
        domain_reqs=$(jq -r --arg d "$domain" '[.requirements[] | select(.domain == $d and .status != "removed") | .id] | .[]' "$DIGEST_DIR/requirements.json")
        local total=0 planned=0 dispatched=0 running=0 merged=0 uncovered=0

        while IFS= read -r req_id; do
            [[ -z "$req_id" ]] && continue
            total=$((total + 1))
            local status
            status=$(jq -r --arg id "$req_id" '.coverage[$id].status // "uncovered"' "$DIGEST_DIR/coverage.json")
            case "$status" in
                planned)     planned=$((planned + 1)) ;;
                dispatched)  dispatched=$((dispatched + 1)) ;;
                running)     running=$((running + 1)) ;;
                merged)      merged=$((merged + 1)) ;;
                *)           uncovered=$((uncovered + 1)) ;;
            esac
        done <<< "$domain_reqs"

        printf "  %-20s total=%d  planned=%d  dispatched=%d  running=%d  merged=%d" \
            "$domain" "$total" "$planned" "$dispatched" "$running" "$merged"
        if [[ $uncovered -gt 0 ]]; then
            printf "  UNCOVERED=%d" "$uncovered"
        fi
        echo ""
    done <<< "$domains"

    # Orphaned entries (removed requirements still in coverage)
    local removed_ids
    removed_ids=$(jq -r '.requirements[] | select(.status == "removed") | .id' "$DIGEST_DIR/requirements.json" 2>/dev/null || true)
    if [[ -n "$removed_ids" ]]; then
        local orphaned=()
        while IFS= read -r rid; do
            [[ -z "$rid" ]] && continue
            if jq -e --arg id "$rid" '.coverage[$id]' "$DIGEST_DIR/coverage.json" &>/dev/null; then
                orphaned+=("$rid")
            fi
        done <<< "$removed_ids"
        if [[ ${#orphaned[@]} -gt 0 ]]; then
            echo ""
            warn "Orphaned coverage entries (requirement removed on re-digest):"
            printf '  %s\n' "${orphaned[@]}"
        fi
    fi

    echo ""
}
