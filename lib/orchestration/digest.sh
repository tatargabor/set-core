#!/usr/bin/env bash
# lib/orchestration/digest.sh — Multi-file spec digest: scan, classify, extract requirements
#
# Sourced by bin/wt-orchestrate after planner.sh.
# Provides: cmd_digest(), cmd_coverage(), scan_spec_directory(), build_digest_prompt(),
#           call_digest_api(), write_digest_output(), validate_digest(), stabilize_ids(),
#           check_digest_freshness(), populate_coverage(), check_coverage_gaps(),
#           update_coverage_status()

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

    # Build prompt and call API
    local digest_prompt
    digest_prompt=$(build_digest_prompt "$abs_spec_path" "$scan_result")

    info "Calling Claude for digest generation..."
    log_info "Digest generation started (files=$file_count, hash=$source_hash)"

    local api_response
    api_response=$(call_digest_api "$digest_prompt") || {
        error "Digest generation failed"
        return 1
    }

    # Parse structured output from response
    local parsed_output
    parsed_output=$(parse_digest_response "$api_response" "$abs_spec_path" "$scan_result") || {
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
    output=$(export RUN_CLAUDE_TIMEOUT=600; echo "$prompt" | run_claude --model "$(model_id opus)") || {
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

# ─── Validation ──────────────────────────────────────────────────────

validate_digest() {
    local parsed="$1"
    local errors=0

    # Check requirements have valid IDs
    local bad_ids
    bad_ids=$(echo "$parsed" | jq -r '.requirements[]? | select(.id | test("^REQ-[A-Z]+-[0-9]+$") | not) | .id' 2>/dev/null || true)
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

    # Write coverage.json
    local uncovered
    uncovered=$(check_coverage_gaps_internal "$coverage")

    jq -n --argjson cov "$coverage" --argjson unc "$uncovered" \
        '{coverage: $cov, uncovered: $unc}' > "$DIGEST_DIR/coverage.json"

    local covered_count
    covered_count=$(echo "$coverage" | jq 'length')
    log_info "Coverage populated: $covered_count requirements mapped"

    # Warn about uncovered
    local unc_count
    unc_count=$(echo "$uncovered" | jq 'length')
    if [[ "$unc_count" -gt 0 ]]; then
        local unc_list
        unc_list=$(echo "$uncovered" | jq -r '.[]' | tr '\n' ', ')
        warn "Warning: $unc_count uncovered requirement(s): $unc_list"
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

    printf '%s\n' "${uncovered[@]}" | jq -R . | jq -s . 2>/dev/null || echo '[]'
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

    log_info "Coverage status updated: $change_name → $new_status"
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
