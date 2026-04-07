#!/usr/bin/env bash
# Deploy shadcn/ui overlay from scaffold to project
# Usage: source this file, then call deploy_shadcn_overlay "$SCAFFOLD_DIR" "$TEST_DIR"

deploy_shadcn_overlay() {
    local scaffold_dir="$1"
    local test_dir="$2"

    if [[ ! -d "$scaffold_dir/shadcn" ]]; then
        return 0  # No overlay — plain Tailwind project
    fi

    echo "[info] Deploying shadcn/ui overlay..."

    # Copy components.json and utils.ts
    cp "$scaffold_dir/shadcn/components.json" "$test_dir/" 2>/dev/null
    mkdir -p "$test_dir/src/lib"
    cp "$scaffold_dir/shadcn/src/lib/utils.ts" "$test_dir/src/lib/" 2>/dev/null

    # Merge extra dependencies into package.json
    if [[ -f "$scaffold_dir/shadcn/deps.json" ]] && [[ -f "$test_dir/package.json" ]]; then
        python3 -c "
import json
with open('$test_dir/package.json') as f:
    pkg = json.load(f)
with open('$scaffold_dir/shadcn/deps.json') as f:
    extra = json.load(f)
for section in ('dependencies', 'devDependencies'):
    if section in extra:
        pkg.setdefault(section, {}).update(extra[section])
with open('$test_dir/package.json', 'w') as f:
    json.dump(pkg, f, indent=2)
"
    fi

    echo "[ok] shadcn/ui overlay deployed (components.json + utils.ts + deps)"
}
