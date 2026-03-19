#!/usr/bin/env bash
# set-memory rules: YAML-based deterministic rules for hook injection
# Dependencies: sourced by bin/set-memory after infra setup

get_rules_file() {
    local toplevel
    toplevel=$(git rev-parse --show-toplevel 2>/dev/null) || true
    if [[ -z "$toplevel" ]]; then
        if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
            toplevel="$CLAUDE_PROJECT_DIR"
        else
            toplevel="$(pwd)"
        fi
    fi
    echo "${toplevel}/.claude/rules.yaml"
}

# Generate a kebab-case id from the first 4 words of a string.
_rules_make_id() {
    local content="$1"
    echo "$content" | tr '[:upper:]' '[:lower:]' | \
        tr -cs 'a-z0-9' '-' | \
        sed 's/^-*//;s/-*$//' | \
        cut -c1-40 | \
        sed 's/-\{2,\}/-/g'
}

# Read .claude/rules.yaml and print rules matching at least one topic in $1 (space-sep prompt text).
# Output format: one line per rule — "id\tcontent"
# Returns 0 even if file is absent or malformed.
_rules_match() {
    local prompt_lower="$1"
    local rules_file
    rules_file=$(get_rules_file)
    [[ -f "$rules_file" ]] || return 0

    python3 - "$rules_file" "$prompt_lower" <<'PYEOF' 2>/dev/null || true
import sys, yaml, re

rules_file = sys.argv[1]
prompt_text = sys.argv[2].lower()

try:
    with open(rules_file) as f:
        data = yaml.safe_load(f)
except Exception:
    sys.exit(0)

if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
    sys.exit(0)

for rule in data["rules"]:
    if not isinstance(rule, dict):
        continue
    topics = rule.get("topics", [])
    content = rule.get("content", "").strip()
    rule_id = rule.get("id", "")
    if not topics or not content:
        continue
    for topic in topics:
        if str(topic).lower() in prompt_text:
            print(f"{rule_id}\t{content}")
            break
PYEOF
}

# cmd_rules dispatcher
cmd_rules() {
    local subcmd="${1:-}"
    shift 2>/dev/null || true

    case "$subcmd" in
        add)    cmd_rules_add "$@" ;;
        list)   cmd_rules_list "$@" ;;
        remove) cmd_rules_remove "$@" ;;
        "")
            echo "Usage: set-memory rules <add|list|remove>" >&2
            echo "  add --topics \"t1,t2\" \"content\"   Add a rule (injected when topics match prompt)" >&2
            echo "  list                              List all rules" >&2
            echo "  remove <id>                       Remove a rule by id" >&2
            return 1
            ;;
        *)
            echo "Error: Unknown rules subcommand '$subcmd'" >&2
            return 1
            ;;
    esac
}

cmd_rules_add() {
    local topics=""
    local content=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --topics) topics="$2"; shift 2 ;;
            *) content="$1"; shift ;;
        esac
    done

    if [[ -z "$content" ]]; then
        echo "Error: content required (e.g., set-memory rules add --topics \"sql,customer\" \"Use customer_ro / XYZ123\")" >&2
        return 1
    fi
    if [[ -z "$topics" ]]; then
        echo "Error: --topics required (comma-separated keywords, e.g., --topics \"sql,customer\")" >&2
        return 1
    fi

    local rules_file
    rules_file=$(get_rules_file)
    mkdir -p "$(dirname "$rules_file")"

    # Generate id from content
    local id
    id=$(_rules_make_id "$content")
    # Truncate to first 4 "words" worth (max 40 chars already handled)
    id=$(echo "$id" | cut -c1-40)

    python3 - "$rules_file" "$id" "$topics" "$content" <<'PYEOF'
import sys, yaml, os

rules_file, rule_id, topics_str, content = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

topics = [t.strip() for t in topics_str.split(",") if t.strip()]

data = {"rules": []}
if os.path.exists(rules_file):
    try:
        with open(rules_file) as f:
            loaded = yaml.safe_load(f)
        if isinstance(loaded, dict) and isinstance(loaded.get("rules"), list):
            data = loaded
    except Exception:
        pass

# Ensure unique id
existing_ids = {r.get("id") for r in data["rules"] if isinstance(r, dict)}
base_id = rule_id
counter = 2
while rule_id in existing_ids:
    rule_id = f"{base_id}-{counter}"
    counter += 1

data["rules"].append({"id": rule_id, "topics": topics, "content": content})

with open(rules_file, "w") as f:
    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

print(f"Rule added: {rule_id}")
print(f"  topics: {', '.join(topics)}")
print(f"  file:   {rules_file}")
PYEOF
}

cmd_rules_list() {
    local rules_file
    rules_file=$(get_rules_file)

    if [[ ! -f "$rules_file" ]]; then
        echo "No rules file found at: $rules_file"
        echo "Use 'set-memory rules add --topics \"t1,t2\" \"content\"' to create one."
        return 0
    fi

    python3 - "$rules_file" <<'PYEOF'
import sys, yaml

rules_file = sys.argv[1]
try:
    with open(rules_file) as f:
        data = yaml.safe_load(f)
except Exception as e:
    print(f"Error reading rules file: {e}", file=sys.stderr)
    sys.exit(1)

rules = data.get("rules", []) if isinstance(data, dict) else []
if not rules:
    print("No rules defined.")
    sys.exit(0)

print(f"Rules ({len(rules)}):")
print()
for rule in rules:
    if not isinstance(rule, dict):
        continue
    rid = rule.get("id", "(no id)")
    topics = ", ".join(rule.get("topics", []))
    content = rule.get("content", "").strip()
    preview = content[:120] + ("..." if len(content) > 120 else "")
    print(f"  [{rid}]")
    print(f"    topics:  {topics}")
    print(f"    content: {preview}")
    print()
PYEOF
}

cmd_rules_remove() {
    local rule_id="${1:-}"
    if [[ -z "$rule_id" ]]; then
        echo "Error: rule id required (use 'set-memory rules list' to see ids)" >&2
        return 1
    fi

    local rules_file
    rules_file=$(get_rules_file)

    if [[ ! -f "$rules_file" ]]; then
        echo "Error: no rules file found at: $rules_file" >&2
        return 1
    fi

    python3 - "$rules_file" "$rule_id" <<'PYEOF'
import sys, yaml

rules_file, rule_id = sys.argv[1], sys.argv[2]

try:
    with open(rules_file) as f:
        data = yaml.safe_load(f)
except Exception as e:
    print(f"Error reading rules file: {e}", file=sys.stderr)
    sys.exit(1)

rules = data.get("rules", []) if isinstance(data, dict) else []
new_rules = [r for r in rules if isinstance(r, dict) and r.get("id") != rule_id]

if len(new_rules) == len(rules):
    print(f"Error: rule '{rule_id}' not found", file=sys.stderr)
    sys.exit(1)

data["rules"] = new_rules
with open(rules_file, "w") as f:
    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

print(f"Rule removed: {rule_id}")
PYEOF
}
