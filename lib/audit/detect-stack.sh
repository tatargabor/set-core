#!/usr/bin/env bash
# Stack detection — identify project framework, package manager, and key dependencies
# Exports: STACK_FRAMEWORK, STACK_PKG_MANAGER, STACK_TYPESCRIPT, STACK_DEPS (comma-separated)
# Also sets STACK_*_CONFIG variables pointing to detected config files

STACK_FRAMEWORK=""
STACK_FRAMEWORK_CONFIG=""
STACK_PKG_MANAGER=""
STACK_TYPESCRIPT=false
STACK_DEPS=""

detect_stack() {
    local project_path="$1"

    # ── Framework detection ──────────────────────────────────────────────
    if ls "$project_path"/next.config.* &>/dev/null; then
        STACK_FRAMEWORK="nextjs"
        STACK_FRAMEWORK_CONFIG=$(ls "$project_path"/next.config.* 2>/dev/null | head -1)
    elif ls "$project_path"/astro.config.* &>/dev/null; then
        STACK_FRAMEWORK="astro"
        STACK_FRAMEWORK_CONFIG=$(ls "$project_path"/astro.config.* 2>/dev/null | head -1)
    elif ls "$project_path"/nuxt.config.* &>/dev/null; then
        STACK_FRAMEWORK="nuxt"
        STACK_FRAMEWORK_CONFIG=$(ls "$project_path"/nuxt.config.* 2>/dev/null | head -1)
    elif ls "$project_path"/svelte.config.* &>/dev/null; then
        STACK_FRAMEWORK="svelte"
        STACK_FRAMEWORK_CONFIG=$(ls "$project_path"/svelte.config.* 2>/dev/null | head -1)
    elif ls "$project_path"/vite.config.* &>/dev/null; then
        STACK_FRAMEWORK="vite"
        STACK_FRAMEWORK_CONFIG=$(ls "$project_path"/vite.config.* 2>/dev/null | head -1)
    elif [[ -f "$project_path/manage.py" ]]; then
        STACK_FRAMEWORK="django"
    elif [[ -f "$project_path/Cargo.toml" ]]; then
        STACK_FRAMEWORK="rust"
    elif [[ -f "$project_path/go.mod" ]]; then
        STACK_FRAMEWORK="go"
    fi

    # ── Package manager detection ────────────────────────────────────────
    if [[ -f "$project_path/pnpm-lock.yaml" ]]; then
        STACK_PKG_MANAGER="pnpm"
    elif [[ -f "$project_path/yarn.lock" ]]; then
        STACK_PKG_MANAGER="yarn"
    elif [[ -f "$project_path/bun.lockb" ]] || [[ -f "$project_path/bun.lock" ]]; then
        STACK_PKG_MANAGER="bun"
    elif [[ -f "$project_path/package-lock.json" ]]; then
        STACK_PKG_MANAGER="npm"
    elif [[ -f "$project_path/Pipfile.lock" ]] || [[ -f "$project_path/poetry.lock" ]]; then
        STACK_PKG_MANAGER="pip"
    fi

    # ── TypeScript detection ─────────────────────────────────────────────
    if [[ -f "$project_path/tsconfig.json" ]]; then
        STACK_TYPESCRIPT=true
    fi

    # ── Key dependency detection from package.json ───────────────────────
    local deps=""
    if [[ -f "$project_path/package.json" ]]; then
        # Extract dependency names (both deps and devDeps)
        local all_deps
        all_deps=$(jq -r '(.dependencies // {} | keys[]) , (.devDependencies // {} | keys[])' "$project_path/package.json" 2>/dev/null)

        local -a detected=()
        echo "$all_deps" | grep -q "^prisma$" && detected+=("prisma")
        echo "$all_deps" | grep -q "^drizzle-orm$" && detected+=("drizzle")
        echo "$all_deps" | grep -q "^tailwindcss$" && detected+=("tailwind")
        echo "$all_deps" | grep -q "^@shadcn" && detected+=("shadcn")
        echo "$all_deps" | grep -q "^next-intl$" && detected+=("next-intl")
        echo "$all_deps" | grep -q "^@supabase" && detected+=("supabase")
        echo "$all_deps" | grep -q "^@anthropic-ai" && detected+=("anthropic-sdk")
        echo "$all_deps" | grep -q "^openai$" && detected+=("openai-sdk")
        echo "$all_deps" | grep -q "^vitest$" && detected+=("vitest")
        echo "$all_deps" | grep -q "^playwright" && detected+=("playwright")
        echo "$all_deps" | grep -q "^knip$" && detected+=("knip")
        echo "$all_deps" | grep -q "^eslint$" && detected+=("eslint")
        echo "$all_deps" | grep -q "^next-auth$" && detected+=("next-auth")

        STACK_DEPS=$(IFS=','; echo "${detected[*]}")
    fi
}

# Get safe commands recommendation based on detected stack
get_recommended_safe_commands() {
    local cmds=()

    # Package manager commands
    case "$STACK_PKG_MANAGER" in
        pnpm) cmds+=("Bash(pnpm lint *)" "Bash(pnpm build *)" "Bash(pnpm test *)") ;;
        npm)  cmds+=("Bash(npm run *)") ;;
        yarn) cmds+=("Bash(yarn lint *)" "Bash(yarn build *)" "Bash(yarn test *)") ;;
        bun)  cmds+=("Bash(bun run *)") ;;
    esac

    # Framework-specific
    case "$STACK_FRAMEWORK" in
        nextjs) cmds+=("Bash(npx next *)") ;;
        astro)  cmds+=("Bash(npx astro *)") ;;
    esac

    # TypeScript
    if $STACK_TYPESCRIPT; then
        cmds+=("Bash(npx tsc *)")
    fi

    # Git (always)
    cmds+=("Bash(git status *)" "Bash(git diff *)" "Bash(git log *)" "Bash(git add *)" "Bash(git commit *)")

    # OpenSpec (if present)
    cmds+=("Bash(openspec *)")

    printf '%s\n' "${cmds[@]}"
}

# Get source file extensions to scan based on stack
get_source_extensions() {
    local exts=()

    case "$STACK_FRAMEWORK" in
        nextjs|vite) exts+=("ts" "tsx" "js" "jsx") ;;
        astro)       exts+=("ts" "tsx" "js" "jsx" "astro") ;;
        svelte)      exts+=("ts" "js" "svelte") ;;
        nuxt)        exts+=("ts" "js" "vue") ;;
        django)      exts+=("py") ;;
        rust)        exts+=("rs") ;;
        go)          exts+=("go") ;;
        *)           exts+=("ts" "tsx" "js" "jsx" "py") ;;
    esac

    printf '%s\n' "${exts[@]}"
}
