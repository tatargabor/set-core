#!/usr/bin/env bash
# Detect E2E_PROJECT if not already set.
# Finds the latest "done" project from the set-web API.
# Exports E2E_PROJECT for downstream commands.
#
# Usage: eval $(scripts/detect-e2e-project.sh)
#   or:  source <(scripts/detect-e2e-project.sh)
#   or:  scripts/detect-e2e-project.sh  (sets E2E_PROJECT in current env via export)

if [[ -n "$E2E_PROJECT" ]]; then
    echo "export E2E_PROJECT=$E2E_PROJECT"
    exit 0
fi

PROJECT=$(curl -sf http://localhost:7400/api/projects 2>/dev/null | python3 -c "
import sys, json
try:
    projects = json.load(sys.stdin)
    done = [p for p in projects if p.get('status') == 'done' and p.get('changes_merged', 0) > 0]
    done.sort(key=lambda p: p.get('last_updated', ''), reverse=True)
    if done:
        print(done[0]['name'])
except:
    pass
" 2>/dev/null)

if [[ -z "$PROJECT" ]]; then
    echo "ERROR: No 'done' project found. Set E2E_PROJECT manually." >&2
    exit 1
fi

echo "Auto-detected project: $PROJECT" >&2
export E2E_PROJECT="$PROJECT"
echo "export E2E_PROJECT=$PROJECT"
