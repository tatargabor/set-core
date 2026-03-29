from __future__ import annotations

"""Loop prompt building: detect next change action, build Claude prompts.

1:1 migration of lib/loop/prompt.sh.
"""

import json
import os
import re
from typing import Optional


def detect_next_change_action(wt_path: str, target_change: str = "") -> str:
    """Detect the next OpenSpec change action needed.

    Returns: "ff:<change-name>" or "apply:<change-name>" or "done" or "none"
    """
    if target_change:
        return _detect_for_target(wt_path, target_change)

    return _detect_scan_all(wt_path)


def build_claude_prompt(
    task: str,
    iteration: int,
    max_iter: int,
    wt_path: str,
    done_criteria: str = "tasks",
    target_change: str = "",
    team_mode: bool = False,
) -> str:
    """Assemble CLI prompt with context injection."""
    state_file = os.path.join(wt_path, ".claude", "loop-state.json")

    # Previous commits
    prev_commits = ""
    if os.path.isfile(state_file):
        try:
            with open(state_file, "r") as f:
                data = json.load(f)
            commits = []
            for it in data.get("iterations", []):
                commits.extend(it.get("commits", []))
            if commits:
                prev_commits = ", ".join(commits)
        except (json.JSONDecodeError, OSError):
            pass

    prev_text = (
        f"Previous iterations made commits: {prev_commits}"
        if prev_commits
        else "This is the first iteration."
    )

    # Detect OpenSpec action
    change_action = ""
    specific_task = ""
    openspec_instructions = ""

    if (
        os.path.isdir(os.path.join(wt_path, "openspec"))
        and done_criteria == "openspec"
        and target_change
    ):
        change_action = detect_next_change_action(wt_path, target_change)

        if change_action.startswith("ff:"):
            change_name = change_action[3:]
            specific_task = f"Create artifacts for the '{change_name}' change"
            openspec_instructions = (
                f"\n# YOUR TASK (MANDATORY — do this and ONLY this)\n"
                f"Run: /opsx:ff {change_name}\n"
                f"This will create design.md, specs, and tasks.md for the '{change_name}' change.\n"
                f"Do NOT implement any code. Do NOT work on any other changes.\n"
                f"After /opsx:ff completes, commit the artifacts and stop.\n"
            )
        elif change_action.startswith("apply:"):
            change_name = change_action[6:]
            specific_task = f"Implement the '{change_name}' change"
            openspec_instructions = (
                f"\n# YOUR TASK (MANDATORY — do this and ONLY this)\n"
                f"Run: /opsx:apply {change_name}\n"
                f"This will implement the tasks defined in tasks.md for the '{change_name}' change.\n"
                f"Do NOT work on any other changes. Focus ONLY on '{change_name}'.\n"
                f"After implementation, commit your changes and stop.\n"
            )
        elif change_action == "done":
            specific_task = "All changes are complete"
            openspec_instructions = (
                "\n# ALL CHANGES COMPLETE\n"
                "All OpenSpec changes have been implemented. There is nothing left to do.\n"
                "Do NOT write any files. Do NOT create any commits. Simply stop.\n"
            )

    effective_task = specific_task or task

    # Reflection section (skip when all changes done — prevents dirty files)
    reflection_section = ""
    if change_action != "done":
        reflection_section = (
            "\n# Reflection (MANDATORY — last step before finishing)\n"
            "Before you stop, write .claude/reflection.md with 3-5 bullet points:\n"
            "- Errors you encountered and how you fixed them\n"
            "- Non-obvious things you learned about this codebase\n"
            "- Workarounds or gotchas the next iteration should know about\n"
            'If nothing notable happened, write "No notable issues." to the file.'
        )

    # Manual tasks instruction
    manual_task_instruction = ""
    from .loop_tasks import find_tasks_file

    tasks_file = find_tasks_file(wt_path)
    if tasks_file and os.path.isfile(tasks_file):
        try:
            with open(tasks_file, "r") as f:
                manual_count = len(re.findall(r"^\s*-\s*\[\?\]", f.read(), re.MULTILINE))
            if manual_count > 0:
                manual_task_instruction = (
                    "\n# Manual Tasks\n"
                    "Tasks marked with [?] in tasks.md require human action "
                    "(e.g., providing API keys, external setup).\n"
                    "Do NOT attempt to complete [?] tasks — skip them entirely "
                    "and focus only on [ ] tasks.\n"
                    "If all [ ] tasks are done but [?] tasks remain, commit your work and stop."
                )
        except OSError:
            pass

    # Team instructions
    team_instructions = ""
    if (
        team_mode
        and change_action != "done"
        and not change_action.startswith("ff:")
    ):
        team_instructions = _build_team_instructions()

    # Previous iteration learnings
    prior_learnings = ""
    prior_content = get_previous_iteration_summary(wt_path)
    if prior_content:
        prior_learnings = (
            f"\n# Previous Iteration Learned\n{prior_content}\n"
        )

    return (
        f"# Task\n{effective_task}\n\n"
        f"# Context\n"
        f"This is iteration {iteration} of {max_iter} in an autonomous Ralph loop.\n"
        f"Previous work is visible in the git history and current file state.\n\n"
        f"# Instructions\n"
        f"1. Read CLAUDE.md first — it contains the project workflow and specific instructions\n"
        f"2. Follow the workflow described in CLAUDE.md exactly\n"
        f"3. Do ONLY what is specified in YOUR TASK above — nothing more\n"
        f"4. If stuck on the same issue, try a different approach\n"
        f"{openspec_instructions}"
        f"{manual_task_instruction}"
        f"{team_instructions}"
        f"\n# Previous Work\n{prev_text}\n\n"
        f"{prior_learnings}"
        f"# Important\n"
        f"- Do ONLY the task specified above — do NOT work on other changes\n"
        f"- CLAUDE.md is the authoritative source for your workflow — follow it\n"
        f"- Commit your changes before exiting\n"
        f"{reflection_section}"
    )


# ─── Context injection helpers ────────────────────────────────


def get_spec_context(wt_path: str, change_name: str) -> str:
    """Read spec files for a change, return combined text."""
    change_dir = os.path.join(wt_path, "openspec", "changes", change_name)
    specs_dir = os.path.join(change_dir, "specs")
    if not os.path.isdir(specs_dir):
        return ""
    parts = []
    for root, _, files in os.walk(specs_dir):
        for f in sorted(files):
            if f.endswith(".md"):
                try:
                    with open(os.path.join(root, f), "r") as fh:
                        parts.append(fh.read())
                except OSError:
                    pass
    return "\n\n---\n\n".join(parts)


def get_design_context(wt_path: str, change_name: str) -> str:
    """Read design.md for a change."""
    path = os.path.join(wt_path, "openspec", "changes", change_name, "design.md")
    try:
        with open(path, "r") as f:
            return f.read()
    except OSError:
        return ""


def get_proposal_context(wt_path: str, change_name: str) -> str:
    """Read proposal.md for a change."""
    path = os.path.join(wt_path, "openspec", "changes", change_name, "proposal.md")
    try:
        with open(path, "r") as f:
            return f.read()
    except OSError:
        return ""


def get_previous_iteration_summary(wt_path: str) -> str:
    """Read .claude/reflection.md if exists."""
    path = os.path.join(wt_path, ".claude", "reflection.md")
    try:
        with open(path, "r") as f:
            return f.read()
    except OSError:
        return ""


# ─── Internal helpers ─────────────────────────────────────────


def _detect_for_target(wt_path: str, target_change: str) -> str:
    """Detect action for a specific change."""
    change_dir = os.path.join(wt_path, "openspec", "changes", target_change)
    tasks_file = os.path.join(change_dir, "tasks.md")

    if not os.path.isdir(change_dir):
        # Check if archived
        archive_dir = os.path.join(wt_path, "openspec", "changes", "archive")
        if os.path.isdir(archive_dir):
            for d in os.listdir(archive_dir):
                if d.endswith(f"-{target_change}") or d == target_change:
                    return "done"
        return "none"

    if not os.path.isfile(tasks_file):
        return f"ff:{target_change}"

    # Count unchecked tasks
    try:
        with open(tasks_file, "r") as f:
            unchecked = len(re.findall(r"^\s*-\s*\[\s*\]", f.read(), re.MULTILINE))
    except OSError:
        unchecked = 0

    if unchecked > 0:
        return f"apply:{target_change}"

    # All tasks checked — but is there actual implementation code?
    # If tasks are [x] but no src/ files were added (stale branch from failed run),
    # force re-implementation instead of declaring done.
    from .git_utils import run_git
    diff_result = run_git(
        "diff", "--name-only", "main...HEAD", "--", "src/", "app/", "lib/", "components/", "pages/",
        cwd=wt_path,
    )
    impl_files = [f for f in diff_result.stdout.strip().splitlines() if f]
    if not impl_files:
        # Tasks checked but no implementation files — stale artifact-only branch
        return f"apply:{target_change}"

    return "done"


def _detect_scan_all(wt_path: str) -> str:
    """Scan all changes to find next action."""
    change_order = []

    # Check for numbered benchmark files
    benchmark_dir = os.path.join(wt_path, "docs", "benchmark")
    if os.path.isdir(benchmark_dir):
        for f in sorted(os.listdir(benchmark_dir)):
            if re.match(r"\d+.*\.md$", f):
                name = re.sub(r"^\d+-", "", f.rsplit(".", 1)[0])
                change_order.append(name)

    # Fallback: alphabetical from openspec/changes
    if not change_order:
        changes_dir = os.path.join(wt_path, "openspec", "changes")
        if os.path.isdir(changes_dir):
            for d in sorted(os.listdir(changes_dir)):
                if d == "archive":
                    continue
                if os.path.isdir(os.path.join(changes_dir, d)):
                    change_order.append(d)

    if not change_order:
        return "none"

    for idx, change in enumerate(change_order, 1):
        change_dir = os.path.join(wt_path, "openspec", "changes", change)
        tasks_file = os.path.join(change_dir, "tasks.md")

        # Check results file
        nn = f"{idx:02d}"
        if os.path.isfile(os.path.join(wt_path, "results", f"change-{nn}.json")):
            continue

        if not os.path.isdir(change_dir):
            # Check if archived
            archive_check = os.path.join(
                wt_path, "openspec", "changes", "archive", change
            )
            if os.path.isdir(archive_check):
                continue
            return f"ff:{change}"

        if not os.path.isfile(tasks_file):
            return f"ff:{change}"

        # Count unchecked
        try:
            with open(tasks_file, "r") as f:
                unchecked = len(
                    re.findall(r"^\s*-\s*\[\s*\]", f.read(), re.MULTILINE)
                )
        except OSError:
            unchecked = 0

        if unchecked > 0:
            return f"apply:{change}"

    return "done"


def _build_team_instructions() -> str:
    """Build Agent Teams instructions block for the prompt."""
    return """
# Agent Teams — Parallel Task Execution

You have Agent Teams available to parallelize independent tasks within this iteration.

## When to Use Teams
- You have **3 or more independent tasks** that don't share files
- Tasks are implementation work (code changes), not planning or artifact creation
- The tasks can run simultaneously without conflicts

## When NOT to Use Teams
- Fewer than 3 independent tasks — work sequentially instead
- Tasks modify the same files (risk of conflicts)
- Tasks have dependencies on each other (task B needs task A's output)
- You're running /opsx:ff (artifact creation) — always sequential
- Only 1-2 tasks remain

## How to Use Teams

1. **Check for orphan teams first**: If ~/.claude/teams/ has leftover team dirs from a previous iteration, clean them up with TeamDelete before proceeding.

2. **Analyze tasks**: Read tasks.md and identify which unchecked tasks are independent (don't share files).

3. **Create a team**: Use TeamCreate with a descriptive team_name.

4. **Create tasks**: Use TaskCreate for each parallelizable task with clear descriptions.

5. **Spawn teammates** (max 3): Use the Agent tool for each teammate:
   - `subagent_type: "general-purpose"` (full tool access)
   - `mode: "bypassPermissions"` (no permission prompts)
   - `team_name: "<your-team>"` (joins the team)
   - Give each a clear prompt describing exactly which task(s) to implement
   - Run teammates in foreground (NOT background) — wait for results

6. **Teammates work**: Each teammate reads the relevant files, makes changes, and marks their tasks complete via TaskUpdate. Teammates do NOT create git commits.

7. **You commit**: After ALL teammates finish, review the combined changes, resolve any conflicts, and create a single coherent commit. Only YOU (the team lead) commit.

8. **Cleanup**: Send shutdown_request to each teammate, wait for shutdown_response, then call TeamDelete.

## Important Rules
- Maximum 3 teammates per iteration
- Only the team lead (you) creates git commits
- If a teammate reports a conflict or error, handle it yourself after they finish
- Always clean up teams before the iteration ends (TeamDelete)
- Mark tasks in tasks.md as [x] after verifying the implementation
"""
