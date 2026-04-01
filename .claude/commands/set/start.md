Start orchestration via the manager API — launches sentinel in the background.

Usage: /set:start [spec-path]

Examples:
  /set:start docs/spec.md
  /set:start docs/v2-release.md
  /set:start                      (auto-detect spec)

## Instructions

Start a sentinel-supervised orchestration run via the web manager API.

### Step 1: Detect project

```bash
# Get project name from current directory
PROJECT_NAME=$(basename "$(pwd)")
echo "Project: $PROJECT_NAME"
```

### Step 2: Find spec file

If a spec path is provided as argument, use it. Otherwise auto-detect:

```bash
# Auto-detect spec files
ls docs/spec.md docs/v*.md docs/*.md 2>/dev/null | head -5
```

If multiple specs found, use AskUserQuestion to let the user choose.

### Step 3: Verify manager is running

```bash
curl -s http://localhost:7400/api/projects 2>/dev/null | python3 -c "
import sys,json
try:
    projects = json.load(sys.stdin)
    names = [p['name'] for p in projects]
    print('Manager: running')
    print(f'Projects: {len(names)}')
except:
    print('Manager: NOT RUNNING — start with: systemctl --user start set-web')
"
```

If manager is not running, tell the user to start it first.

### Step 4: Check project is registered

Verify the current project appears in the manager's project list. If not:

```bash
# Register first
set-project init --name $PROJECT_NAME --project-type web --template nextjs
systemctl --user restart set-web
sleep 3
```

### Step 5: Start sentinel

```bash
curl -X POST http://localhost:7400/api/$PROJECT_NAME/sentinel/start \
  -H 'Content-Type: application/json' \
  -d "{\"spec\":\"$SPEC_PATH\"}"
```

Parse the response:
- `{"status": "ok", "pid": 12345}` → Success, show PID and dashboard link
- Error → Show error message

### Step 6: Show status

```
Sentinel started for $PROJECT_NAME
  PID: $PID
  Spec: $SPEC_PATH
  Dashboard: http://localhost:7400

Monitor:
  curl -s http://localhost:7400/api/$PROJECT_NAME/status | python3 -m json.tool
```
