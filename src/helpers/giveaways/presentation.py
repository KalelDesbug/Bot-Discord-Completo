from __future__ import annotations

from datetime import datetime, timezone

import discord

from src.utils.functions import SafeLayoutView


def parse_colour(value: str | None) -> discord.Colour:
    raw = (value or "#5865F2").strip().lstrip("#")
    try:
        return discord.Colour(int(raw, 16)) if len(raw) == 6 else discord.Colour.blurple()
    except ValueError:
        return discord.Colour.blurple()


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _add_image(container: discord.ui.Container, url: str | None) -> None:
    if url:
        container.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(media=url)))


def build_active_giveaway_view(giveaway: dict) -> discord.ui.LayoutView:
    from src.components.buttons.giveaways import GiveawayJoinButton, GiveawayParticipantsButton

    view = SafeLayoutView(timeout=None)
    colour = parse_colour(giveaway.get("color"))
    container = discord.ui.Container(accent_colour=colour)

    title = giveaway.get("title") or giveaway.get("prize") or "Sorteio"
    description = (giveaway.get("description") or "Participe clicando no botão abaixo.").strip()
    participant_count = int(giveaway.get("participant_count", 0))
    total_entries = int(giveaway.get("total_entries", 0))
    winners_count = int(giveaway.get("winners_count", 1))
    ends_at = as_utc(giveaway["ends_at"])
    prize = giveaway.get("prize") or title
    requirement_text = (giveaway.get("requirement_text") or "Sem requisitos").strip()

    bonus_description = (giveaway.get("bonus_description") or "").strip()
    details = [
        f"# 🎉 {title}",
        description,
        "",
        f"🏆 **Prêmio:** {prize}",
        (f"✨ **Bônus:** {bonus_description}" if bonus_description else (f"✨ **Bônus:** entradas extras automáticas por cargo" if giveaway.get("role_bonus") else "✨ **Participação:** aberta aos membros elegíveis")),
        f"👥 **Participantes:** {participant_count}",
        f"🎟️ **Entradas computadas:** {total_entries}",
        f"🏅 **Ganhadores:** {winners_count}",
        f"📋 **Requisitos:** {requirement_text}",
        f"⏰ **Acaba:** <t:{int(ends_at.timestamp())}:F> (<t:{int(ends_at.timestamp())}:R>)",
    ]
    container.add_item(discord.ui.TextDisplay("\n".join(details)))

    thumbnail_url = giveaway.get("thumbnail_url")
    if thumbnail_url:
        container.add_item(discord.ui.Section(
            discord.ui.TextDisplay("-# Clique em **Participar** para registrar sua entrada."),
            accessory=discord.ui.Thumbnail(media=thumbnail_url),
        ))

    _add_image(container, giveaway.get("image_url"))
    container.add_item(discord.ui.Separator())
    row = discord.ui.ActionRow()
    row.add_item(GiveawayJoinButton(giveaway["_id"], label=f"Participar ({participant_count})"))
    if giveaway.get("show_participants", True):
        row.add_item(GiveawayParticipantsButton(giveaway["_id"]))
    container.add_item(row)
    view.add_item(container)
    return view


def build_finished_giveaway_view(giveaway: dict) -> discord.ui.LayoutView:
    view = SafeLayoutView(timeout=None)
    colour = parse_colour(giveaway.get("color"))
    container = discord.ui.Container(accent_colour=colour)
    title = giveaway.get("title") or giveaway.get("prize") or "Sorteio"
    prize = giveaway.get("prize") or title
    winners = giveaway.get("winners", [])
    winner_entries = giveaway.get("winner_entries", {})

    lines = [
        f"# 🏁 {title}",
        giveaway.get("description") or "O sorteio foi encerrado.",
        "",
        f"🏆 **Prêmio:** {prize}",
        f"👥 **Participantes:** {int(giveaway.get('participant_count', 0))}",
        "",
        "## 🎉 Resultado",
    ]
    if winners:
        lines.extend(f"{index}. <@{winner_id}> — {int(winner_entries.get(str(winner_id), 1))} entrada(s)" for index, winner_id in enumerate(winners, start=1))
    else:
        lines.append("Ninguém participou desta vez. Não houve ganhadores.")
    ended_at = giveaway.get("ended_at")
    if ended_at:
        lines += ["", f"-# Encerrado em <t:{int(as_utc(ended_at).timestamp())}:F> • ID: `{giveaway['_id']}`"]
    container.add_item(discord.ui.TextDisplay("\n".join(lines)))
    _add_image(container, giveaway.get("image_url"))
    view.add_item(container)
    return view
