from __future__ import annotations

import asyncio
import html
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import discord


HTML_HEADER = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transcript - {channel_name}</title>
<style>
body {{ background:#313338; color:#dbdee1; font-family:sans-serif; padding:20px; }}
.msg {{ margin-bottom:14px; }}
.author {{ font-weight:bold; color:#f2f3f5; }}
.time {{ color:#949ba4; font-size:12px; margin-left:8px; }}
.content {{ margin-top:2px; white-space:pre-wrap; overflow-wrap:anywhere; }}
a {{ color:#00a8fc; }}
</style>
</head>
<body>
<h2>Transcript de #{channel_name}</h2>
"""
HTML_FOOTER = "\n</body>\n</html>\n"


@dataclass(slots=True)
class TranscriptArtifact:
    path: Path
    filename: str

    def discord_file(self) -> discord.File:
        return discord.File(self.path.open("rb"), filename=self.filename)

    def cleanup(self) -> None:
        self.path.unlink(missing_ok=True)


def message_record(message: discord.Message) -> dict[str, Any]:
    return {
        "channel_id": message.channel.id,
        "message_id": message.id,
        "guild_id": message.guild.id,
        "author_id": message.author.id,
        "author_name": str(message.author),
        "content": message.content or "",
        "created_at": message.created_at.isoformat(),
        "attachments": [
            {"filename": attachment.filename, "url": attachment.url}
            for attachment in message.attachments
        ],
    }


async def sync_ticket_history(channel: discord.TextChannel, database) -> None:
    """Imports only messages not yet persisted, in bounded batches."""
    after_id = await database.ticket_history_cursor(channel.id)
    after = discord.Object(id=after_id) if after_id is not None else None
    batch: list[dict[str, Any]] = []

    async for message in channel.history(limit=None, after=after, oldest_first=True):
        batch.append(message_record(message))
        if len(batch) >= 100:
            await database.save_ticket_messages(batch, update_history_cursor=True)
            batch.clear()

    if batch:
        await database.save_ticket_messages(batch, update_history_cursor=True)


def _format_timestamp(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M:%S")
    except (TypeError, ValueError):
        return value


def _render_html_message(message: dict[str, Any]) -> str:
    author = html.escape(message["author_name"])
    timestamp = html.escape(_format_timestamp(message["created_at"]))
    content = html.escape(message.get("content") or "")
    for attachment in message.get("attachments", []):
        filename = html.escape(str(attachment.get("filename") or "Anexo"))
        url = html.escape(str(attachment.get("url") or ""), quote=True)
        if url:
            content += f'<br><a href="{url}" rel="noopener noreferrer">{filename}</a>'
        else:
            content += f"<br>{filename}"
    return (
        '<div class="msg"><span class="author">'
        f"{author}</span><span class=\"time\">{timestamp}</span>"
        f'<div class="content">{content or "&nbsp;"}</div></div>\n'
    )


def _render_text_message(message: dict[str, Any]) -> str:
    content = message.get("content") or ""
    attachments = message.get("attachments", [])
    for attachment in attachments:
        filename = attachment.get("filename") or "Anexo"
        url = attachment.get("url") or ""
        content += f"\n[Anexo: {filename}] {url}".rstrip()
    return (
        f"[{_format_timestamp(message['created_at'])}] "
        f"{message['author_name']} ({message['author_id']}): {content}\n"
    )


async def generate_transcript_artifact(
    channel: discord.TextChannel,
    database,
    output_format: Literal["html", "txt"] = "txt",
    page_size: int = 250,
) -> TranscriptArtifact:
    safe_page_size = min(1000, max(1, int(page_size)))
    await sync_ticket_history(channel, database)

    suffix = ".html" if output_format == "html" else ".txt"
    filename = f"transcript-{channel.name}{suffix}"
    temporary = tempfile.NamedTemporaryFile(
        mode="wb",
        prefix="discord-ticket-transcript-",
        suffix=suffix,
        delete=False,
    )
    path = Path(temporary.name)

    try:
        with temporary as output:
            if output_format == "html":
                title = html.escape(channel.name)
                output.write(HTML_HEADER.format(channel_name=title).encode("utf-8"))
            else:
                output.write(
                    f"Transcript de #{channel.name}\n{'=' * 40}\n\n".encode("utf-8")
                )

            after_id = 0
            while True:
                page = await database.get_ticket_message_page(
                    channel.id,
                    after_message_id=after_id,
                    limit=safe_page_size,
                )
                if not page:
                    break

                rendered_page = [
                    (
                        _render_html_message(message)
                        if output_format == "html"
                        else _render_text_message(message)
                    )
                    for message in page
                ]
                page_bytes = "".join(rendered_page).encode("utf-8", errors="replace")
                await asyncio.to_thread(output.write, page_bytes)

                after_id = page[-1]["message_id"]
                if len(page) < safe_page_size:
                    break

            if output_format == "html":
                output.write(HTML_FOOTER.encode("utf-8"))

        return TranscriptArtifact(path=path, filename=filename)
    except Exception:
        path.unlink(missing_ok=True)
        raise
