import discord

from src.bot_app.features.logs.service import LogLevel, build_log_embed, friendly_error


def test_log_embed_uses_white_for_startup_and_truncates_long_messages() -> None:
    embed = build_log_embed("Bot ligado", "x" * 5000, LogLevel.STARTUP)

    assert embed.colour == discord.Colour.from_rgb(255, 255, 255)
    assert embed.title == "⚪ Bot ligado"
    assert len(embed.description) == 3500


def test_error_summary_is_short_and_does_not_expose_large_traceback_text() -> None:
    error = RuntimeError("sensitive detail " * 1000)

    message = friendly_error(error)

    assert len(message) < 250
    assert "sensitive detail" not in message
    assert "detalhes técnicos" in message
