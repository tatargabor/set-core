"""A `discord` module that is not discord.py is "not installed", not a startup crash.

Measured 2026-11-23: every set-web start printed a traceback ending in
`AttributeError: module 'discord' has no attribute 'Intents'` — `import discord`
resolved to a namespace directory, so the ImportError branch never ran."""

import asyncio
import logging
import sys
import types

from set_orch.discord import DiscordBot


def test_a_non_discordpy_module_is_one_warning_not_a_crash(monkeypatch, caplog):
    fake = types.ModuleType("discord")
    fake.__path__ = ["/somewhere/discord"]
    monkeypatch.setitem(sys.modules, "discord", fake)
    monkeypatch.setenv("SET_DISCORD_TOKEN", "x")
    bot = DiscordBot({"channel": "c"})
    with caplog.at_level(logging.WARNING, logger="set_orch.discord"):
        asyncio.run(bot.start())  # must not raise
    assert any("discord.py not installed" in r.getMessage() for r in caplog.records)
    assert bot._client is None
