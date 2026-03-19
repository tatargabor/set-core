#!/usr/bin/env bash
# collect-results.sh - Gather all benchmark results into a single JSON report
#
# Usage: ./collect-results.sh <project-dir> <run-label>
# Example: ./collect-results.sh ~/benchmark/run-a/craftbazaar "Run A (baseline)"
# Output: results-<label>.json

set -euo pipefail

PROJECT_DIR="${1:-.}"
RUN_LABEL="${2:-unknown}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$PROJECT_DIR"

echo "=== Collecting results for: $RUN_LABEL ==="

OUTPUT_FILE="results-$(echo "$RUN_LABEL" | tr ' ()' '-' | tr '[:upper:]' '[:lower:]').json"

python3 -c "
import json, subprocess, os, glob

results = {
    'run_label': '$RUN_LABEL',
    'project_dir': os.path.abspath('.'),
}

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except:
        return -1, '', 'error'

# --- Git history ---
code, out, _ = run('git log --oneline --format=\"%h %ai %s\"')
results['git_log'] = out.split('\n') if out else []
results['commit_count'] = len(results['git_log'])

# --- OpenSpec status ---
code, out, _ = run('openspec list --json')
try:
    results['openspec'] = json.loads(out)
except:
    results['openspec'] = out

# --- Agent status files ---
status_files = sorted(glob.glob('results/*.json'))
agent_results = {}
for sf in status_files:
    try:
        with open(sf) as f:
            agent_results[os.path.basename(sf)] = json.load(f)
    except:
        agent_results[os.path.basename(sf)] = 'parse_error'
results['agent_status_files'] = agent_results

# --- Run evaluator scripts ---
eval_dir = '$SCRIPT_DIR'
evaluators = ['eval-schema.sh', 'eval-api.sh', 'eval-behavior.sh', 'eval-coherence.sh']

for ev in evaluators:
    ev_path = os.path.join(eval_dir, ev)
    if os.path.exists(ev_path):
        if 'api' in ev:
            # API evaluator needs port — try to detect
            cmd = f'bash {ev_path} 4000'
        else:
            cmd = f'bash {ev_path} .'
        code, out, err = run(cmd, timeout=120)
        try:
            results[ev.replace('.sh', '')] = json.loads(out)
        except:
            results[ev.replace('.sh', '')] = {'error': out or err}

# --- Test script results ---
test_dir = 'tests'
test_results = {}
if os.path.isdir(test_dir):
    for tf in sorted(glob.glob(os.path.join(test_dir, 'test-*.sh'))):
        tname = os.path.basename(tf)
        code, out, err = run(f'bash {tf} 4000', timeout=30)
        lines = out.split('\n')
        pass_count = sum(1 for l in lines if l.startswith('PASS:'))
        fail_count = sum(1 for l in lines if l.startswith('FAIL:'))
        test_results[tname] = {
            'exit_code': code,
            'passed': pass_count,
            'failed': fail_count,
            'output': out[:500]
        }
results['test_results'] = test_results

# --- Memory data (Run B only) ---
code, out, _ = run('set-memory status --json')
if code == 0:
    try:
        results['memory_status'] = json.loads(out)
    except:
        results['memory_status'] = None

    code2, out2, _ = run('set-memory list --json')
    if code2 == 0:
        try:
            results['memories'] = json.loads(out2)
        except:
            results['memories'] = None

# --- Write output ---
with open('$OUTPUT_FILE', 'w') as f:
    json.dump(results, f, indent=2)

print(f'Results written to: $OUTPUT_FILE')
print(f'Commits: {results[\"commit_count\"]}')
print(f'Agent status files: {len(agent_results)}')
" 2>/dev/null

echo "=== Done ==="
