#!/usr/bin/env bash
# Check: Design documentation — docs/design/*.md coverage

check_design_docs() {
    local project_path="$1"
    local design_dir="$project_path/docs/design"
    local dim="design_docs"

    add_source "$dim" "docs/design/"

    # Standard categories and their detection patterns
    local -a categories=("ui-conventions" "functional-conventions" "data-model" "deployment" "code-hygiene")
    local -a cat_descriptions=(
        "UI patterns, components, spacing, themes"
        "Server actions, auth, DB access, error handling"
        "Database schema, relationships, state machines"
        "Deploy config, env vars, infra"
        "File limits, DRY rules, cleanup policy"
    )

    if [[ ! -d "$design_dir" ]]; then
        add_check "$dim" "design_dir" "fail" "No docs/design/ directory"

        # Build guidance with source pointers based on detected stack
        local sources=""
        sources="READ: src/components/**/* — UI patterns and components"
        sources="${sources}; READ: src/app/**/actions.ts or src/lib/**/* — functional patterns"
        if [[ -f "$project_path/package.json" ]]; then
            sources="${sources}; READ: package.json — framework and dependency context"
        fi
        if [[ -n "$STACK_FRAMEWORK_CONFIG" ]]; then
            sources="${sources}; READ: $(basename "$STACK_FRAMEWORK_CONFIG") — framework config"
        fi
        sources="${sources}; REFERENCE: lib/audit/reference.md#design-documentation"

        add_guidance "$dim" "Create docs/design/ with documentation of actual project patterns" "$sources"
        return
    fi

    local present=0
    local missing_cats=()

    for i in "${!categories[@]}"; do
        local cat="${categories[$i]}"
        local desc="${cat_descriptions[$i]}"
        # Look for files matching the category (flexible naming)
        local found=false
        for f in "$design_dir"/*.md; do
            [[ ! -f "$f" ]] && continue
            local fname
            fname=$(basename "$f" .md)
            if [[ "$fname" == *"$cat"* ]] || [[ "$fname" == *"${cat//-/_}"* ]]; then
                local lines
                lines=$(file_lines "$f")
                local mtime
                mtime=$(file_mtime_human "$f")
                add_check "$dim" "doc_${cat}" "pass" "${fname}.md (${lines} lines, ${mtime})"
                found=true
                present=$((present + 1))
                break
            fi
        done
        if ! $found; then
            missing_cats+=("${cat}:${desc}")
        fi
    done

    # Report missing categories
    if [[ ${#missing_cats[@]} -gt 0 ]]; then
        for mc in "${missing_cats[@]}"; do
            local cat_name="${mc%%:*}"
            local cat_desc="${mc#*:}"
            add_check "$dim" "doc_${cat_name}" "warn" "Missing: ${cat_name} (${cat_desc})"

            # Build guidance sources based on category and stack
            local sources=""
            case "$cat_name" in
                ui-conventions)
                    sources="READ: src/components/**/* — find component patterns"
                    [[ -f "$project_path/src/app/globals.css" ]] && sources="${sources}; READ: src/app/globals.css — theme/color system"
                    [[ -f "$project_path/tailwind.config.ts" ]] && sources="${sources}; READ: tailwind.config.ts"
                    [[ -f "$project_path/tailwind.config.js" ]] && sources="${sources}; READ: tailwind.config.js"
                    sources="${sources}; READ: package.json — UI deps (component library, CSS framework)"
                    ;;
                functional-conventions)
                    sources="READ: src/app/**/actions.ts or src/lib/**/*.ts — server/API patterns"
                    [[ -f "$project_path/src/middleware.ts" ]] && sources="${sources}; READ: src/middleware.ts — auth/routing"
                    sources="${sources}; READ: src/lib/**/* — shared utilities and patterns"
                    ;;
                data-model)
                    [[ -d "$project_path/prisma" ]] && sources="READ: prisma/schema.prisma — DB schema"
                    [[ -d "$project_path/supabase" ]] && sources="${sources:+${sources}; }READ: supabase/migrations/ — DB schema"
                    [[ -d "$project_path/drizzle" ]] && sources="${sources:+${sources}; }READ: drizzle/ — DB schema"
                    [[ -z "$sources" ]] && sources="READ: src/lib/db* or src/models/ — database layer"
                    ;;
                deployment)
                    [[ -f "$project_path/Dockerfile" ]] && sources="READ: Dockerfile"
                    [[ -f "$project_path/docker-compose.yml" ]] && sources="${sources:+${sources}; }READ: docker-compose.yml"
                    [[ -f "$project_path/railway.toml" ]] && sources="${sources:+${sources}; }READ: railway.toml"
                    [[ -f "$project_path/vercel.json" ]] && sources="${sources:+${sources}; }READ: vercel.json"
                    [[ -f "$project_path/fly.toml" ]] && sources="${sources:+${sources}; }READ: fly.toml"
                    [[ -z "$sources" ]] && sources="READ: package.json (scripts section) — build/start commands"
                    sources="${sources}; READ: .env.example or .env* patterns — environment variables"
                    ;;
                code-hygiene)
                    sources="REFERENCE: lib/audit/reference.md#code-hygiene"
                    local has_knip=false
                    file_contains "$project_path/package.json" "knip" && has_knip=true
                    $has_knip && sources="${sources}; READ: knip.config.* — existing unused code config"
                    ;;
            esac
            sources="${sources}; REFERENCE: lib/audit/reference.md#design-documentation"
            add_guidance "$dim" "Create docs/design/${cat_name}.md" "$sources"
        done
    fi

    # Overall status
    if [[ $present -ge 3 ]]; then
        add_check "$dim" "coverage" "pass" "Design docs cover ${present}/${#categories[@]} standard categories"
    elif [[ $present -gt 0 ]]; then
        add_check "$dim" "coverage" "warn" "Design docs cover only ${present}/${#categories[@]} standard categories"
    fi
}
