#!/usr/bin/env bash
# Section 17.2 — verify-pipeline gate for run-history-and-phase-continuity.
#
# Invoked by the openspec-verify-change skill when this change is verified.
# A non-zero exit surfaces a CRITICAL issue in the verification report,
# which in turn blocks /opsx:archive.
#
# This change ships the centralized LineagePaths resolver; the gate ensures
# no code file reintroduces a hardcoded orchestration-path literal outside
# the resolver's allowlist.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "[verify-hook] Running hardcoded-orchestration-path audit..."
if ! bash "$REPO_ROOT/scripts/audit-lineage-paths.sh" \
        --report "$SCRIPT_DIR/audit-report.txt"; then
    echo "[verify-hook] FAIL — see audit-report.txt for residuals." >&2
    exit 1
fi
echo "[verify-hook] PASS — no residual hardcoded literals."
exit 0
