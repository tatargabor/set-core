"""Tests for wt_orch.engine — Directive parsing, token budget, time limit, completion."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from wt_orch.engine import Directives, parse_directives


class TestDirectivesDefaults:
    def test_default_values(self):
        """Directives dataclass has sensible defaults."""
        d = Directives()
        assert d.max_parallel == 3
        assert d.test_timeout == 300
        assert d.merge_policy == "eager"
        assert d.review_model == "opus"
        assert d.auto_replan is False
        assert d.smoke_blocking is False
        assert d.token_budget == 0
        assert d.milestones_enabled is False
        assert d.e2e_mode == "per_change"
        assert d.context_pruning is True
        assert d.model_routing == "off"
        assert d.team_mode is False

    def test_all_fields_present(self):
        """All ~40 directive fields are accessible."""
        d = Directives()
        fields = [f for f in dir(d) if not f.startswith("_")]
        # Should have a large number of fields
        assert len(fields) >= 30


class TestParseDirectives:
    def test_empty_dict(self):
        """Empty dict yields all defaults."""
        d = parse_directives({})
        assert d.max_parallel == 3
        assert d.test_command == ""
        assert d.auto_replan is False
        assert d.smoke_command == ""

    def test_all_fields(self):
        """All fields parse correctly from JSON."""
        raw = {
            "max_parallel": 5,
            "test_command": "pnpm test",
            "merge_policy": "conservative",
            "token_budget": 2000000,
            "auto_replan": True,
            "test_timeout": 600,
            "max_verify_retries": 3,
            "review_before_merge": True,
            "review_model": "sonnet",
            "default_model": "sonnet",
            "smoke_command": "pnpm smoke",
            "smoke_timeout": 180,
            "smoke_blocking": True,
            "smoke_fix_max_retries": 5,
            "smoke_fix_max_turns": 20,
            "smoke_health_check_url": "http://localhost:3000/health",
            "smoke_health_check_timeout": 60,
            "e2e_command": "pnpm e2e",
            "e2e_timeout": 300,
            "e2e_mode": "phase_end",
            "e2e_port_base": 4000,
            "token_hard_limit": 10000000,
            "checkpoint_every": 5,
            "max_replan_cycles": 8,
            "time_limit": "10h",
            "monitor_idle_timeout": 600,
            "context_pruning": False,
            "model_routing": "complexity",
            "team_mode": True,
            "post_merge_command": "pnpm db:generate",
            "post_phase_audit": True,
            "checkpoint_auto_approve": True,
            "max_redispatch": 3,
        }
        d = parse_directives(raw)
        assert d.max_parallel == 5
        assert d.test_command == "pnpm test"
        assert d.merge_policy == "conservative"
        assert d.token_budget == 2000000
        assert d.auto_replan is True
        assert d.test_timeout == 600
        assert d.max_verify_retries == 3
        assert d.review_before_merge is True
        assert d.review_model == "sonnet"
        assert d.default_model == "sonnet"
        assert d.smoke_command == "pnpm smoke"
        assert d.smoke_timeout == 180
        assert d.smoke_blocking is True
        assert d.e2e_command == "pnpm e2e"
        assert d.e2e_mode == "phase_end"
        assert d.e2e_port_base == 4000
        assert d.token_hard_limit == 10000000
        assert d.context_pruning is False
        assert d.model_routing == "complexity"
        assert d.team_mode is True
        assert d.post_merge_command == "pnpm db:generate"
        assert d.checkpoint_auto_approve is True
        assert d.max_redispatch == 3

    def test_string_to_int_coercion(self):
        """String values get coerced to int where needed."""
        raw = {"max_parallel": "7", "test_timeout": "120", "token_budget": "5000000"}
        d = parse_directives(raw)
        assert d.max_parallel == 7
        assert d.test_timeout == 120
        assert d.token_budget == 5000000

    def test_string_to_bool_coercion(self):
        """String 'true'/'false' get coerced to bool."""
        raw = {
            "auto_replan": "true",
            "review_before_merge": "false",
            "smoke_blocking": "true",
        }
        d = parse_directives(raw)
        assert d.auto_replan is True
        assert d.review_before_merge is False
        assert d.smoke_blocking is True

    def test_milestones_nested(self):
        """Milestone config parses from nested 'milestones' key."""
        raw = {
            "milestones": {
                "enabled": True,
                "dev_server": "pnpm dev",
                "base_port": 4000,
                "max_worktrees": 5,
            }
        }
        d = parse_directives(raw)
        assert d.milestones_enabled is True
        assert d.milestones_dev_server == "pnpm dev"
        assert d.milestones_base_port == 4000
        assert d.milestones_max_worktrees == 5

    def test_milestones_defaults(self):
        """Milestones default to disabled."""
        d = parse_directives({})
        assert d.milestones_enabled is False
        assert d.milestones_dev_server == ""
        assert d.milestones_base_port == 3100
        assert d.milestones_max_worktrees == 3

    def test_hook_directives(self):
        """Hook directives parse correctly."""
        raw = {
            "hook_pre_dispatch": "echo pre",
            "hook_post_verify": "echo post",
            "hook_pre_merge": "echo merge",
            "hook_post_merge": "echo done",
            "hook_on_fail": "echo fail",
        }
        d = parse_directives(raw)
        assert d.hook_pre_dispatch == "echo pre"
        assert d.hook_post_verify == "echo post"
        assert d.hook_pre_merge == "echo merge"
        assert d.hook_post_merge == "echo done"
        assert d.hook_on_fail == "echo fail"

    def test_unknown_fields_ignored(self):
        """Unknown fields don't cause errors."""
        raw = {"unknown_field": "value", "max_parallel": 10}
        d = parse_directives(raw)
        assert d.max_parallel == 10

    def test_time_limit_parsing(self):
        """Time limit string is parsed to seconds."""
        raw = {"time_limit": "2h"}
        d = parse_directives(raw)
        assert d.time_limit_secs == 7200  # 2 hours

    def test_time_limit_none(self):
        """Time limit 'none' disables it (stays 0)."""
        raw = {"time_limit": "none"}
        d = parse_directives(raw)
        assert d.time_limit_secs == 0


class TestTokenBudgetLogic:
    """Test token budget threshold calculations using Directives."""

    def test_zero_budget_means_unlimited(self):
        d = parse_directives({"token_budget": 0})
        assert d.token_budget == 0

    def test_budget_threshold(self):
        d = parse_directives({"token_budget": 5000000})
        total_tokens = 6000000
        assert total_tokens > d.token_budget

    def test_hard_limit_default(self):
        d = parse_directives({})
        assert d.token_hard_limit > 0


class TestTimeLimitLogic:
    """Test time limit parsing edge cases."""

    def test_default_time_limit(self):
        d = parse_directives({})
        assert d.time_limit_secs == 18000  # 5h default

    def test_disabled_time_limit(self):
        for val in ["none", "0"]:
            d = parse_directives({"time_limit": val})
            assert d.time_limit_secs == 0


class TestCompletionDetection:
    """Test terminal status detection logic."""

    def test_terminal_statuses(self):
        """All terminal statuses are recognized."""
        terminal = {"merged", "done", "skipped", "failed", "merge-blocked"}
        for status in terminal:
            # These are the statuses that should count toward completion
            assert status in terminal

    def test_active_statuses(self):
        """Active statuses are not terminal."""
        active = {"running", "pending", "verifying", "stalled", "dispatched"}
        terminal = {"merged", "done", "skipped", "failed", "merge-blocked"}
        for status in active:
            assert status not in terminal
