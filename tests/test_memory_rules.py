"""Tests for set-memory rules CLI and hook injection.

4.1 CLI: add / list / remove
4.2 Hook injection: MANDATORY RULES appears when topic matches
4.3 Hook graceful-degrade: missing rules file → no rules section, exit 0
4.4 Hook graceful-degrade: malformed YAML → no rules section, exit 0
"""

import json
import os
import subprocess
import tempfile

import pytest

# Paths
SCRIPT = os.path.join(os.path.dirname(__file__), "..", "bin", "set-memory")
HOOK = os.path.join(os.path.dirname(__file__), "..", "bin", "set-hook-memory")


def run_wt(rules_dir, *args, stdin=None):
    """Run set-memory rules with a tmp project dir. Returns (stdout, stderr, returncode)."""
    env = os.environ.copy()
    env["SHODH_STORAGE"] = rules_dir + "/shodh"  # isolated, unused for rules
    result = subprocess.run(
        [SCRIPT] + list(args),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        cwd=rules_dir,
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def run_hook(project_dir, prompt, session_id="test-hook-123"):
    """Invoke set-hook-memory UserPromptSubmit with a prompt. Returns (stdout, returncode)."""
    payload = json.dumps({"session_id": session_id, "prompt": prompt})
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = project_dir
    env["SHODH_STORAGE"] = project_dir + "/shodh"
    result = subprocess.run(
        [HOOK, "UserPromptSubmit"],
        input=payload,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        cwd=project_dir,
    )
    return result.stdout, result.returncode


def setup_git_repo(tmp_path):
    """Init a minimal git repo so git rev-parse works."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        capture_output=True,
        cwd=str(tmp_path),
        env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t.com",
             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t.com"},
    )
    return str(tmp_path)


# ============================================================
# 4.1 CLI tests
# ============================================================

class TestRulesCLI:
    def test_add_creates_yaml(self, tmp_path):
        """set-memory rules add creates .claude/rules.yaml"""
        project_dir = setup_git_repo(tmp_path)
        stdout, stderr, rc = run_wt(
            project_dir, "rules", "add",
            "--topics", "customer,sql",
            "Use customer_ro / XYZ123 for customer table"
        )
        assert rc == 0, f"exit {rc}: {stderr}"
        assert "Rule added:" in stdout
        rules_file = os.path.join(project_dir, ".claude", "rules.yaml")
        assert os.path.exists(rules_file), "rules.yaml not created"

    def test_add_generates_id(self, tmp_path):
        """set-memory rules add auto-generates a kebab-case id"""
        project_dir = setup_git_repo(tmp_path)
        stdout, _, rc = run_wt(
            project_dir, "rules", "add",
            "--topics", "deploy",
            "Require QA sign-off before deploying"
        )
        assert rc == 0
        # Id should appear in output
        assert "require-qa-sign-off" in stdout or "require" in stdout

    def test_list_shows_rules(self, tmp_path):
        """set-memory rules list shows added rules"""
        project_dir = setup_git_repo(tmp_path)
        run_wt(project_dir, "rules", "add", "--topics", "customer", "Use customer_ro")
        stdout, _, rc = run_wt(project_dir, "rules", "list")
        assert rc == 0
        assert "customer" in stdout
        assert "Use customer_ro" in stdout

    def test_list_empty_no_crash(self, tmp_path):
        """set-memory rules list when no file exists exits 0"""
        project_dir = setup_git_repo(tmp_path)
        stdout, _, rc = run_wt(project_dir, "rules", "list")
        assert rc == 0

    def test_remove_existing_rule(self, tmp_path):
        """set-memory rules remove deletes the rule"""
        project_dir = setup_git_repo(tmp_path)
        add_stdout, _, _ = run_wt(
            project_dir, "rules", "add", "--topics", "sql", "Use sql_ro / pass123"
        )
        # Extract id from add output (first token after "Rule added: ")
        rule_id = None
        for line in add_stdout.splitlines():
            if line.startswith("Rule added:"):
                rule_id = line.split(":", 1)[1].strip()
                break
        assert rule_id, f"could not extract id from: {add_stdout}"

        stdout, _, rc = run_wt(project_dir, "rules", "remove", rule_id)
        assert rc == 0
        assert "Rule removed" in stdout

        # Verify it's gone
        list_out, _, _ = run_wt(project_dir, "rules", "list")
        assert rule_id not in list_out

    def test_remove_nonexistent_exits_1(self, tmp_path):
        """set-memory rules remove nonexistent id exits 1"""
        project_dir = setup_git_repo(tmp_path)
        _, _, rc = run_wt(project_dir, "rules", "remove", "nonexistent-id")
        assert rc == 1

    def test_add_requires_topics(self, tmp_path):
        """set-memory rules add without --topics exits 1"""
        project_dir = setup_git_repo(tmp_path)
        _, _, rc = run_wt(project_dir, "rules", "add", "some content without topics")
        assert rc == 1

    def test_add_requires_content(self, tmp_path):
        """set-memory rules add without content exits 1"""
        project_dir = setup_git_repo(tmp_path)
        _, _, rc = run_wt(project_dir, "rules", "add", "--topics", "sql")
        assert rc == 1


# ============================================================
# 4.2 Hook injection test
# ============================================================

class TestHookInjection:
    def test_mandatory_rules_injected_when_topic_matches(self, tmp_path):
        """MANDATORY RULES section appears when rule topic matches prompt."""
        project_dir = setup_git_repo(tmp_path)

        # Add a rule via CLI
        run_wt(
            project_dir, "rules", "add",
            "--topics", "customer,sql",
            "Use customer_ro / XYZ123 for customer table"
        )

        # Fire hook with matching prompt
        stdout, rc = run_hook(project_dir, "mi a customer tábla tartalma?")
        assert rc == 0

        # Output should contain the MANDATORY RULES section
        assert "MANDATORY RULES" in stdout, f"MANDATORY RULES not in output: {stdout[:500]}"
        assert "customer_ro" in stdout or "XYZ123" in stdout, f"Rule content missing: {stdout[:500]}"

    def test_mandatory_rules_before_project_memory(self, tmp_path):
        """MANDATORY RULES section appears before PROJECT MEMORY."""
        project_dir = setup_git_repo(tmp_path)

        run_wt(
            project_dir, "rules", "add",
            "--topics", "customer",
            "Use customer_ro / XYZ123"
        )

        stdout, rc = run_hook(project_dir, "customer table select")
        assert rc == 0

        if "MANDATORY RULES" in stdout and "PROJECT MEMORY" in stdout:
            mandatory_pos = stdout.index("MANDATORY RULES")
            memory_pos = stdout.index("PROJECT MEMORY")
            assert mandatory_pos < memory_pos, "MANDATORY RULES must appear before PROJECT MEMORY"

    def test_no_rules_section_when_no_match(self, tmp_path):
        """No MANDATORY RULES section when no topic matches."""
        project_dir = setup_git_repo(tmp_path)

        run_wt(
            project_dir, "rules", "add",
            "--topics", "customer,sql",
            "Use customer_ro / XYZ123"
        )

        stdout, rc = run_hook(project_dir, "what is the weather today?")
        assert rc == 0
        assert "MANDATORY RULES" not in stdout


# ============================================================
# 4.3 Graceful degrade: missing rules file
# ============================================================

class TestHookGracefulDegrade:
    def test_missing_rules_file_exits_0(self, tmp_path):
        """Hook exits 0 when no .claude/rules.yaml exists."""
        project_dir = setup_git_repo(tmp_path)
        # Don't create any rules file
        stdout, rc = run_hook(project_dir, "customer sql query")
        assert rc == 0
        assert "MANDATORY RULES" not in stdout

    # ============================================================
    # 4.4 Graceful degrade: malformed YAML
    # ============================================================

    def test_malformed_yaml_exits_0(self, tmp_path):
        """Hook exits 0 and skips rules when .claude/rules.yaml is malformed."""
        project_dir = setup_git_repo(tmp_path)

        # Write invalid YAML
        claude_dir = os.path.join(project_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        with open(os.path.join(claude_dir, "rules.yaml"), "w") as f:
            f.write("rules: [this is: {invalid yaml: : :")

        stdout, rc = run_hook(project_dir, "customer sql query")
        assert rc == 0
        assert "MANDATORY RULES" not in stdout
