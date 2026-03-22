"""Tests for Discord webhook notifications."""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestResolveWebhookUrl:
    """Test _resolve_webhook_url() priority order."""

    def setup_method(self):
        # Reset cache between tests
        import set_orch.notifications as n
        n._webhook_url_cache = None
        n._webhook_url_resolved = False

    def test_env_var_highest_priority(self):
        from set_orch.notifications import _resolve_webhook_url
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://env.example.com/webhook"}):
            assert _resolve_webhook_url() == "https://env.example.com/webhook"

    def test_discord_json_fallback(self, tmp_path):
        from set_orch.notifications import _resolve_webhook_url
        config = tmp_path / "discord.json"
        config.write_text(json.dumps({"webhook_url": "https://json.example.com/webhook"}))

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISCORD_WEBHOOK_URL", None)
            with patch("set_orch.notifications.Path.home", return_value=tmp_path / "fake"):
                # Need to put the file where the code looks
                config_dir = tmp_path / "fake" / ".config" / "set-core"
                config_dir.mkdir(parents=True)
                (config_dir / "discord.json").write_text(
                    json.dumps({"webhook_url": "https://json.example.com/webhook"})
                )
                url = _resolve_webhook_url()
                assert url == "https://json.example.com/webhook"

    def test_returns_empty_when_nothing_configured(self):
        from set_orch.notifications import _resolve_webhook_url
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISCORD_WEBHOOK_URL", None)
            with patch("set_orch.notifications.Path.home", return_value=Path("/nonexistent")):
                assert _resolve_webhook_url() == ""


class TestSendDiscordWebhook:
    """Test _send_discord_webhook() builds correct embed JSON."""

    def test_normal_urgency_green(self):
        from set_orch.notifications import _send_discord_webhook
        with patch("subprocess.run") as mock_run:
            _send_discord_webhook(
                "https://example.com/webhook",
                "change merged: auth", "25K tokens", "normal", "micro-web"
            )
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            payload = json.loads(call_args[-1])  # -d argument
            assert payload["embeds"][0]["color"] == 0x2ECC71
            assert "auth" in payload["embeds"][0]["title"]
            assert payload["embeds"][0]["footer"]["text"] == "micro-web"

    def test_critical_urgency_red(self):
        from set_orch.notifications import _send_discord_webhook
        with patch("subprocess.run") as mock_run:
            _send_discord_webhook(
                "https://example.com/webhook",
                "STUCK", "no progress", "critical", "test-proj"
            )
            payload = json.loads(mock_run.call_args[0][0][-1])
            assert payload["embeds"][0]["color"] == 0xE74C3C

    def test_truncates_long_body(self):
        from set_orch.notifications import _send_discord_webhook
        with patch("subprocess.run") as mock_run:
            _send_discord_webhook(
                "https://example.com/webhook",
                "title", "x" * 3000, "normal", "proj"
            )
            payload = json.loads(mock_run.call_args[0][0][-1])
            assert len(payload["embeds"][0]["description"]) == 2000


class TestAutoEnable:
    """Test auto-enable adds discord to channels when webhook configured."""

    def test_auto_enables_when_webhook_set(self):
        from set_orch.notifications import send_notification
        with patch("set_orch.notifications._resolve_webhook_url", return_value="https://example.com/wh"), \
             patch("set_orch.notifications._send_discord_webhook") as mock_wh, \
             patch("subprocess.run"):  # for notify-send
            send_notification("test", "body", channels="desktop")
            mock_wh.assert_called_once()

    def test_no_auto_enable_without_webhook(self):
        from set_orch.notifications import send_notification
        with patch("set_orch.notifications._resolve_webhook_url", return_value=""), \
             patch("set_orch.notifications._send_discord_sync") as mock_bot, \
             patch("subprocess.run"):
            send_notification("test", "body", channels="desktop")
            mock_bot.assert_not_called()
