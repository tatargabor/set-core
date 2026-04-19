#!/usr/bin/env bash
# Section 17.7 — install an opt-in pre-push git hook that runs the
# hardcoded-orchestration-path audit. Non-zero exit refuses the push so
# a regression cannot reach the remote.
#
# Usage:
#   scripts/install-lineage-audit-hook.sh          # install into .git/hooks/pre-push
#   scripts/install-lineage-audit-hook.sh --remove # remove the hook
#
# The hook is deliberately opt-in: set-core contributors and downstream
# forks decide per-clone whether to enforce the gate locally.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOK_PATH="$REPO_ROOT/.git/hooks/pre-push"

if [[ "${1:-}" == "--remove" ]]; then
    if [[ -f "$HOOK_PATH" ]] && grep -q "audit-lineage-paths.sh" "$HOOK_PATH" 2>/dev/null; then
        rm -f "$HOOK_PATH"
        echo "Removed pre-push hook: $HOOK_PATH"
    else
        echo "No lineage-audit pre-push hook to remove."
    fi
    exit 0
fi

mkdir -p "$(dirname "$HOOK_PATH")"

cat > "$HOOK_PATH" <<'HOOK'
#!/usr/bin/env bash
# Pre-push hook: block pushes that contain hardcoded orchestration-path
# literals outside the LineagePaths resolver.  Installed by
# scripts/install-lineage-audit-hook.sh.

set -e
REPO_ROOT="$(git rev-parse --show-toplevel)"
if [[ -x "$REPO_ROOT/scripts/audit-lineage-paths.sh" ]]; then
    if ! bash "$REPO_ROOT/scripts/audit-lineage-paths.sh" >/dev/null; then
        echo "pre-push: hardcoded-path audit FAILED — run:"
        echo "  bash scripts/audit-lineage-paths.sh"
        echo "and migrate the residuals to LineagePaths before pushing."
        exit 1
    fi
fi
HOOK

chmod +x "$HOOK_PATH"
echo "Installed pre-push hook: $HOOK_PATH"
echo "Remove with: $0 --remove"
