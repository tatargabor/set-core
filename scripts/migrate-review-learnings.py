#!/usr/bin/env python3
"""Migrate review-findings.jsonl from past E2E runs into template learnings JSONL.

Scans ~/.local/share/set-core/e2e-runs/*/set/orchestration/review-findings.jsonl,
extracts CRITICAL/HIGH patterns, deduplicates, classifies via profile, and writes
to ~/.config/set-core/review-learnings/<profile>.jsonl.

Usage:
    python scripts/migrate-review-learnings.py [--dry-run] [--run-dir DIR ...]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))


def find_run_dirs() -> list[Path]:
    """Find all E2E run directories with review-findings.jsonl."""
    base = Path(os.environ.get(
        "XDG_DATA_HOME",
        Path.home() / ".local" / "share",
    )) / "set-core" / "e2e-runs"
    if not base.is_dir():
        return []
    results = []
    for d in sorted(base.iterdir()):
        f = d / "wt" / "orchestration" / "review-findings.jsonl"
        if f.is_file():
            results.append(f)
    return results


def extract_patterns(findings_path: Path) -> list[dict]:
    """Extract deduplicated CRITICAL/HIGH patterns from a findings JSONL."""
    patterns: list[dict] = []
    seen: set[str] = set()
    run_name = findings_path.parent.parent.parent.name  # e.g. craftbrew-run8

    with open(findings_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            change = entry.get("change", "unknown")
            for issue in entry.get("issues", []):
                sev = issue.get("severity", "")
                if sev not in ("CRITICAL", "HIGH"):
                    continue
                summary = re.sub(
                    r"\[(?:CRITICAL|HIGH)\]\s*", "", issue.get("summary", "")
                ).strip()
                # Skip NOT_FIXED false positives
                if summary.startswith("NOT_FIXED"):
                    continue
                norm = summary.lower()[:60]
                if norm and norm not in seen:
                    seen.add(norm)
                    patterns.append({
                        "pattern": summary,
                        "severity": sev,
                        "fix_hint": issue.get("fix", ""),
                        "source_changes": [f"{run_name}/{change}"],
                    })
    return patterns


def main():
    parser = argparse.ArgumentParser(description="Migrate review findings to template learnings")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written without writing")
    parser.add_argument("--run-dir", action="append", help="Specific run dir(s) to process (default: auto-discover)")
    parser.add_argument("--profile", default=None, help="Profile name for output JSONL (default: auto-detect, fallback 'web')")
    args = parser.parse_args()

    # Discover findings files
    if args.run_dir:
        findings_files = []
        for d in args.run_dir:
            f = Path(d) / "wt" / "orchestration" / "review-findings.jsonl"
            if f.is_file():
                findings_files.append(f)
            else:
                print(f"WARNING: No review-findings.jsonl in {d}")
    else:
        findings_files = find_run_dirs()

    if not findings_files:
        print("No review-findings.jsonl files found.")
        return

    print(f"Found {len(findings_files)} findings file(s):")
    for f in findings_files:
        print(f"  {f}")

    # Extract all patterns
    all_patterns: list[dict] = []
    for f in findings_files:
        patterns = extract_patterns(f)
        print(f"  {f.parent.parent.parent.name}: {len(patterns)} CRITICAL/HIGH patterns")
        all_patterns.extend(patterns)

    if not all_patterns:
        print("\nNo CRITICAL/HIGH patterns found.")
        return

    # Deduplicate across runs
    by_key: dict[str, dict] = {}
    for p in all_patterns:
        key = re.sub(r"\[(?:CRITICAL|HIGH)\]\s*", "", p["pattern"]).strip().lower()[:60]
        if key in by_key:
            by_key[key]["count"] = by_key[key].get("count", 1) + 1
            for sc in p.get("source_changes", []):
                if sc not in by_key[key]["source_changes"]:
                    by_key[key]["source_changes"].append(sc)
        else:
            by_key[key] = {
                "pattern": p["pattern"],
                "severity": p["severity"],
                "scope": "template",  # migration always writes to template
                "count": 1,
                "last_seen": "2026-03-22T00:00:00+00:00",
                "source_changes": p.get("source_changes", []),
                "fix_hint": p.get("fix_hint", ""),
            }

    unique = list(by_key.values())
    # Cap at 50
    if len(unique) > 50:
        unique = unique[:50]

    print(f"\n{len(all_patterns)} total → {len(unique)} unique patterns after dedup")

    if args.dry_run:
        print("\n--- DRY RUN: would write these patterns ---")
        for p in unique:
            print(f"  [{p['severity']}] {p['pattern'][:80]}")
            print(f"    seen {p['count']}x from {p['source_changes']}")
            if p.get("fix_hint"):
                print(f"    fix: {p['fix_hint'][:60]}")
        return

    # Determine profile name
    if args.profile:
        profile_name = args.profile
    else:
        try:
            from set_orch.profile_loader import load_profile
            profile = load_profile()
            profile_name = profile.info.name
            if profile_name == "null":
                profile_name = "web"
                print("INFO: NullProfile detected (not in a project dir), using 'web'")
        except Exception:
            profile_name = "web"
            print(f"WARNING: Could not load profile, using default name '{profile_name}'")

    # Write to template JSONL
    config_base = Path(os.environ.get("XDG_CONFIG_HOME", "")) if os.environ.get("XDG_CONFIG_HOME") else Path.home() / ".config"
    out_dir = config_base / "set-core" / "review-learnings"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{profile_name}.jsonl"

    # Merge with existing if present
    existing: list[dict] = []
    if out_path.is_file():
        with open(out_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        existing.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    if existing:
        print(f"Merging with {len(existing)} existing entries in {out_path}")
        # Use profile's merge logic
        try:
            from set_orch.profile_types import ProjectType
            merged = ProjectType._merge_learnings(existing, unique, "2026-03-22T00:00:00+00:00")
        except Exception:
            # Fallback: just append deduped
            merged = existing + unique
    else:
        merged = unique

    with open(out_path, "w") as f:
        for entry in merged:
            f.write(json.dumps(entry) + "\n")

    print(f"\nWrote {len(merged)} patterns to {out_path}")


if __name__ == "__main__":
    main()
