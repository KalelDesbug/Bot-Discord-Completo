from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.utils.functions import build_notice, is_giveaway_manager, permission_denied_view
from src.components.buttons.giveaways import GiveawayJoinButton, GiveawayParticipantsButton
from src.helpers.giveaways.presentation import as_utc, build_active_giveaway_view, build_finished_giveaway_view
from src.helpers.giveaways.setup_ui import GiveawaySetupView


class GiveawayCog(commands.Cog):
    giveaway = app_commands.Group(name="giveaway", description="Cria e gerencia sorteios")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        if not self.poll_due_giveaways.is_running():
            self.poll_due_giveaways.start()

    async def cog_unload(self) -> None:
        self.poll_due_giveaways.cancel()

    async def _authorized(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(view=build_notice("❌ Este comando só pode ser usado dentro de um servidor.", discord.Colour.red()), ephemeral=True)
            return False
        if not is_giveaway_manager(interaction.user):
            await interaction.response.send_message(view=permission_denied_view(), ephemeral=True)
            return False
        return True

    @giveaway.command(name="entrada-extra", description="Concede entradas extras a um participante após verificar uma tarefa")
    @app_commands.guild_only()
    @app_commands.describe(
        giveaway_id="ID do sorteio ativo",
        usuario="Participante que concluiu a tarefa",
        quantidade="Quantidade de entradas extras (1 a 100)",
        motivo="Motivo do bônus, como tarefa diária concluída",
    )
    async def extra_entries_command(
        self,
        interaction: discord.Interaction,
        giveaway_id: str,
        usuario: discord.Member,
        quantidade: app_commands.Range[int, 1, 100],
        motivo: str = "Tarefa concluída",
    ) -> None:
        if not await self._authorized(interaction):
            return
        giveaway_id = giveaway_id.strip().lower()
        doc = await self.bot.db.get_giveaway(giveaway_id)
        if not doc or doc.get("guild_id") != interaction.guild.id or doc.get("status") != "active":
            await interaction.response.send_message(view=build_notice("❌ O sorteio não existe neste servidor ou já foi encerrado.", discord.Colour.red()), ephemeral=True)
            return
        if usuario.bot:
            await interaction.response.send_message(view=build_notice("❌ Não é possível conceder entradas a um bot.", discord.Colour.red()), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        added = await self.bot.db.add_giveaway_entries(
            giveaway_id, usuario.id, int(quantidade), interaction.user.id, motivo.strip() or "Tarefa concluída"
        )
        if not added:
            await interaction.followup.send(view=build_notice("❌ Esse membro ainda não está participando do sorteio ou ele acabou de ser encerrado.", discord.Colour.orange()), ephemeral=True)
            return
        updated = await self.bot.db.get_giveaway(giveaway_id)
        channel = interaction.guild.get_channel(updated.get("channel_id")) if updated else None
        if isinstance(channel, discord.TextChannel) and updated.get("message_id"):
            try:
                message = await channel.fetch_message(updated["message_id"])
                await message.edit(view=build_active_giveaway_view(updated))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        await interaction.followup.send(
            view=build_notice(f"✅ Concedidas **{quantidade}** entrada(s) extra(s) a {usuario.mention}.\n**Motivo:** {motivo[:300]}", discord.Colour.green()),
            ephemeral=True,
        )

    @giveaway.command(name="setup", description="Abre o painel para configurar e iniciar um sorteio")
    @app_commands.guild_only()
    async def setup_giveaway(self, interaction: discord.Interaction) -> None:
        if not await self._authorized(interaction):
            return
        view = GiveawaySetupView(self.bot, interaction.guild, interaction.user.id, interaction)
        await interaction.response.send_message(view=view, ephemeral=True)

    @giveaway.command(name="encerrar", description="Encerra um sorteio ativo pelo ID")
    @app_commands.guild_only()
    @app_commands.describe(giveaway_id="ID do sorteio exibido no painel ou no resultado")
    async def end_giveaway_command(self, interaction: discord.Interaction, giveaway_id: str) -> None:
        if not await self._authorized(interaction):
            return
        giveaway_id = giveaway_id.strip().lower()
        if len(giveaway_id) != 32 or any(char not in "0123456789abcdef" for char in giveaway_id):
            await interaction.response.send_message(view=build_notice("❌ ID inválido. Use o ID hexadecimal de 32 caracteres do sorteio.", discord.Colour.red()), ephemeral=True)
            return
        doc = await self.bot.db.get_giveaway(giveaway_id)
        if not doc or doc.get("guild_id") != interaction.guild.id:
            await interaction.response.send_message(view=build_notice("❌ Não encontrei esse sorteio neste servidor.", discord.Colour.red()), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        success = await self.finish_giveaway(giveaway_id, force=True)
        if success:
            await interaction.followup.send(view=build_notice(f"✅ Sorteio **{doc.get('title', doc.get('prize', 'Sorteio'))}** encerrado e resultado publicado.", discord.Colour.green()), ephemeral=True)
        else:
            await interaction.followup.send(view=build_notice("⚠️ Esse sorteio já foi encerrado ou está sendo processado.", discord.Colour.orange()), ephemeral=True)

    @giveaway.command(name="reroll", description="Sorteia novos ganhadores para um sorteio encerrado")
    @app_commands.guild_only()
    @app_commands.describe(giveaway_id="ID do sorteio encerrado")
    async def reroll_giveaway_command(self, interaction: discord.Interaction, giveaway_id: str) -> None:
        if not await self._authorized(interaction):
            return
        giveaway_id = giveaway_id.strip().lower()
        doc = await self.bot.db.get_giveaway(giveaway_id)
        if not doc or doc.get("guild_id") != interaction.guild.id:
            await interaction.response.send_message(view=build_notice("❌ Não encontrei esse sorteio neste servidor.", discord.Colour.red()), ephemeral=True)
            return
        if doc.get("status") != "ended":
            await interaction.response.send_message(view=build_notice("⚠️ Só é possível sortear novamente após o encerramento.", discord.Colour.orange()), ephemeral=True)
            return

        previous = {str(user_id) for user_id in doc.get("winners", [])}
        selected = await self.bot.db.select_giveaway_winners(
            giveaway_id,
            int(doc.get("winners_count", 1)),
            excluded=previous,
        )
        winners = [int(item["user_id"]) for item in selected]
        if not winners:
            await interaction.response.send_message(view=build_notice("❌ Não há participantes elegíveis novos para sortear.", discord.Colour.red()), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        all_winners = list(doc.get("winners", [])) + winners
        winner_entries = dict(doc.get("winner_entries", {}))
        winner_entries.update({item["user_id"]: item["entries"] for item in selected})
        reroll_count = int(doc.get("reroll_count", 0)) + 1
        await self.bot.db.update_giveaway(giveaway_id, {
            "winners": all_winners,
            "winner_entries": winner_entries,
            "reroll_count": reroll_count,
            "last_reroll_at": datetime.now(timezone.utc),
        })
        updated = await self.bot.db.get_giveaway(giveaway_id)
        await self._refresh_finished_message(updated)
        await self._announce_winners(updated, winners, reroll=True)
        await interaction.followup.send(
            view=build_notice(f"✅ Novo sorteio realizado. Novos ganhadores: {', '.join(f'<@{uid}>' for uid in winners)}", discord.Colour.green()),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @giveaway.command(name="ativos", description="Lista os sorteios ativos deste servidor")
    @app_commands.guild_only()
    async def list_giveaways_command(self, interaction: discord.Interaction) -> None:
        if not await self._authorized(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        cursor = self.bot.db.giveaways.find({"guild_id": interaction.guild.id, "status": "active"}).sort("ends_at", 1).limit(10)
        docs = [doc async for doc in cursor]
        if not docs:
            await interaction.followup.send(view=build_notice("Não há sorteios ativos neste servidor.", discord.Colour.blurple()), ephemeral=True)
            return
        lines = ["## 🎉 Sorteios ativos"]
        for doc in docs:
            end_at = as_utc(doc["ends_at"])
            lines.append(
                f"**{doc.get('title', doc.get('prize', 'Sorteio'))}** — {doc.get('participant_count', 0)} participante(s)\n"
                f"Canal: <#{doc.get('channel_id')}> • Termina <t:{int(end_at.timestamp())}:R>\n"
                f"ID: `{doc['_id']}`"
            )
        await interaction.followup.send(view=build_notice("\n\n".join(lines), discord.Colour.blurple()), ephemeral=True)

    async def create_from_setup(self, interaction: discord.Interaction, setup_view: GiveawaySetupView) -> None:
        draft = setup_view.draft
        channel_id = draft.get("channel_id")
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(view=build_notice("❌ Selecione um canal de texto válido na aba **Geral**.", discord.Colour.red()), ephemeral=True)
            return
        me = interaction.guild.me
        permissions = channel.permissions_for(me) if me else None
        if not permissions or not permissions.view_channel or not permissions.send_messages:
            await interaction.response.send_message(view=build_notice("❌ Não tenho permissão para visualizar e enviar mensagens no canal escolhido.", discord.Colour.red()), ephemeral=True)
            return
        if not str(draft.get("title", "")).strip() or not str(draft.get("prize", "")).strip():
            await interaction.response.send_message(view=build_notice("❌ Defina o nome do sorteio e o prêmio antes de iniciar.", discord.Colour.red()), ephemeral=True)
            return
        if set(map(int, draft.get("allowed_roles", []))) & set(map(int, draft.get("blocked_roles", []))):
            await interaction.response.send_message(view=build_notice("❌ Um mesmo cargo não pode estar nas listas de permitidos e bloqueados.", discord.Colour.red()), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        now = datetime.now(timezone.utc)
        giveaway_id = uuid.uuid4().hex
        doc = {
            "_id": giveaway_id,
            "guild_id": interaction.guild.id,
            "channel_id": channel.id,
            "message_id": None,
            "status": "creating",
            "title": draft["title"].strip(),
            "description": draft.get("description", ""),
            "prize": draft["prize"].strip(),
            "requirement_text": draft.get("requirement_text", "Sem requisitos"),
            "image_url": draft.get("image_url"),
            "thumbnail_url": draft.get("thumbnail_url"),
            "color": draft.get("color", "#5865F2"),
            "duration_seconds": int(draft.get("duration_seconds", 3600)),
            "winners_count": int(draft.get("winners_count", 1)),
            "allowed_roles": [int(value) for value in draft.get("allowed_roles", [])],
            "blocked_roles": [int(value) for value in draft.get("blocked_roles", [])],
            "role_bonus": {str(key): int(value) for key, value in draft.get("role_bonus", {}).items()},
            "bonus_description": draft.get("bonus_description", ""),
            "show_participants": bool(draft.get("show_participants", True)),
            "announce_winners": bool(draft.get("announce_winners", True)),
            "dm_winners": bool(draft.get("dm_winners", False)),
            "winner_instructions": draft.get("winner_instructions", ""),
            "participants": {},
            "participant_count": 0,
            "total_entries": 0,
            "winners": [],
            "reroll_count": 0,
            "created_by": interaction.user.id,
            "created_at": now,
            "ends_at": now + timedelta(seconds=int(draft.get("duration_seconds", 3600))),
        }
        await self.bot.db.create_giveaway(doc)
        try:
            message = await channel.send(
                view=build_active_giveaway_view(doc),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (discord.Forbidden, discord.HTTPException) as error:
            await self.bot.db.delete_giveaway(giveaway_id)
            await interaction.edit_original_response(view=build_notice(f"❌ Não consegui publicar o sorteio no canal escolhido ({type(error).__name__}). Confira minhas permissões.", discord.Colour.red()))
            return

        await self.bot.db.update_giveaway(giveaway_id, {
            "status": "active",
            "message_id": message.id,
        })
        doc["status"] = "active"
        doc["message_id"] = message.id
        try:
            await message.edit(view=build_active_giveaway_view(doc))
        except discord.HTTPException:
            pass

        await interaction.edit_original_response(view=build_notice(
            "✅ **Sorteio iniciado!**\n"
            f"Publicação: {message.jump_url}\n"
            f"ID para encerrar ou sortear novamente: `{giveaway_id}`\n"
            f"O encerramento automático está programado para <t:{int(doc['ends_at'].timestamp())}:F>.",
            discord.Colour.green(),
        ))

    async def handle_join(self, interaction: discord.Interaction, giveaway_id: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        doc = await self.bot.db.get_giveaway(giveaway_id)
        if not doc or doc.get("guild_id") != (interaction.guild.id if interaction.guild else None):
            await interaction.followup.send(view=build_notice("❌ Este sorteio não foi encontrado neste servidor.", discord.Colour.red()), ephemeral=True)
            return
        if doc.get("status") != "active" or as_utc(doc["ends_at"]) <= datetime.now(timezone.utc):
            if doc.get("status") == "active":
                await self.finish_giveaway(giveaway_id, force=False)
            await interaction.followup.send(view=build_notice("⏰ Este sorteio já foi encerrado.", discord.Colour.orange()), ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            await interaction.followup.send(view=build_notice("❌ Entre pelo servidor para participar.", discord.Colour.red()), ephemeral=True)
            return
        member = interaction.user
        if member.bot:
            await interaction.followup.send(view=build_notice("❌ Bots não podem participar de sorteios.", discord.Colour.red()), ephemeral=True)
            return

        role_ids = {role.id for role in member.roles}
        allowed_roles = {int(value) for value in doc.get("allowed_roles", [])}
        blocked_roles = {int(value) for value in doc.get("blocked_roles", [])}
        if allowed_roles and not role_ids.intersection(allowed_roles):
            await interaction.followup.send(view=build_notice("❌ Você não possui nenhum dos cargos exigidos para participar.", discord.Colour.red()), ephemeral=True)
            return
        if role_ids.intersection(blocked_roles):
            await interaction.followup.send(view=build_notice("❌ Você possui um cargo que bloqueia sua participação neste sorteio.", discord.Colour.red()), ephemeral=True)
            return

        participant_key = str(member.id)
        existing_participant = await self.bot.db.get_giveaway_participant(giveaway_id, member.id)
        if existing_participant:
            entries = int(existing_participant.get("entries", 1))
            await interaction.followup.send(view=build_notice(f"Você já está participando deste sorteio com **{entries}** entrada(s).", discord.Colour.blurple()), ephemeral=True)
            return

        bonus_map = {str(key): int(value) for key, value in doc.get("role_bonus", {}).items()}
        extra = sum(value for role_id, value in bonus_map.items() if int(role_id) in role_ids)
        entries = 1 + extra
        joined = await self.bot.db.join_giveaway(giveaway_id, member.id, entries, datetime.now(timezone.utc))
        if not joined:
            existing_participant = await self.bot.db.get_giveaway_participant(giveaway_id, member.id)
            if existing_participant:
                current_entries = int(existing_participant.get("entries", 1))
                text = f"Você já está participando deste sorteio com **{current_entries}** entrada(s)."
            else:
                text = "O sorteio foi encerrado ou sua participação não pôde ser registrada. Tente novamente."
            await interaction.followup.send(view=build_notice(text, discord.Colour.orange()), ephemeral=True)
            return

        latest = await self.bot.db.get_giveaway(giveaway_id)
        if latest and interaction.message:
            try:
                await interaction.message.edit(view=build_active_giveaway_view(latest))
            except discord.HTTPException:
                pass
        await interaction.followup.send(
            view=build_notice(f"✅ Você está participando! Foram registradas **{entries}** entrada(s). Boa sorte!", discord.Colour.green()),
            ephemeral=True,
        )

    async def handle_participants(self, interaction: discord.Interaction, giveaway_id: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        doc = await self.bot.db.get_giveaway(giveaway_id)
        if not doc or doc.get("guild_id") != (interaction.guild.id if interaction.guild else None):
            await interaction.followup.send(view=build_notice("❌ Este sorteio não foi encontrado neste servidor.", discord.Colour.red()), ephemeral=True)
            return

        participants = await self.bot.db.get_giveaway_participants_page(giveaway_id, limit=25)
        participant_count = int(doc.get("participant_count", 0))
        lines = [f"## 👥 Participantes — {doc.get('title', 'Sorteio')}", f"Total: **{participant_count}** participante(s) • **{int(doc.get('total_entries', 0))}** entrada(s)", ""]
        if not participants:
            lines.append("Ainda não há participantes.")
        else:
            for index, participant in enumerate(participants, start=1):
                lines.append(f"{index}. <@{participant['user_id']}> — {int(participant.get('entries', 1))} entrada(s)")
            if participant_count > len(participants):
                lines.append(f"\n-# Exibindo os primeiros {len(participants)} de {participant_count} participantes.")
        await interaction.followup.send(
            view=build_notice("\n".join(lines), discord.Colour.blurple()),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def finish_giveaway(self, giveaway_id: str, force: bool = False) -> bool:
        doc = await self.bot.db.get_giveaway(giveaway_id)
        if not doc:
            return False
        now = datetime.now(timezone.utc)
        if doc.get("status") == "active":
            if not force and as_utc(doc["ends_at"]) > now:
                return False
            claimed = await self.bot.db.claim_giveaway_end(giveaway_id, force=force, now=now)
            if not claimed:
                return False
        elif doc.get("status") == "ending":
            stale_before = now - timedelta(minutes=2)
            ending_at = doc.get("ending_at")
            if ending_at and as_utc(ending_at) > stale_before:
                return False
            claimed = await self.bot.db.recover_giveaway_end(giveaway_id, stale_before, now=now)
            if not claimed:
                return False
        else:
            return False

        # Re-read after claiming the close so entries accepted just before the
        # status transition are included in the weighted draw.
        doc = await self.bot.db.get_giveaway(giveaway_id)
        if not doc:
            return False
        selected = await self.bot.db.select_giveaway_winners(
            giveaway_id,
            int(doc.get("winners_count", 1)),
        )
        winners = [int(item["user_id"]) for item in selected]
        winner_entries = {item["user_id"]: item["entries"] for item in selected}
        await self.bot.db.update_giveaway(giveaway_id, {
            "status": "ended",
            "winners": winners,
            "winner_entries": winner_entries,
            "ended_at": now,
            "total_entries": int(doc.get("total_entries", 0)),
        })
        ended = await self.bot.db.get_giveaway(giveaway_id)
        await self._refresh_finished_message(ended)
        if ended.get("announce_winners", True):
            await self._announce_winners(ended, winners)
        if ended.get("dm_winners", False) and winners:
            await self._dm_winners(ended, winners)
        return True

    @tasks.loop(seconds=30)
    async def poll_due_giveaways(self) -> None:
        for doc in await self.bot.db.due_giveaways(datetime.now(timezone.utc)):
            try:
                await self.finish_giveaway(doc["_id"], force=False)
            except Exception as error:
                logging.getLogger("discord.giveaways").exception(
                    "Falha ao finalizar sorteio %s", doc.get("_id"),
                    exc_info=(type(error), error, error.__traceback__),
                )

    @poll_due_giveaways.before_loop
    async def before_poll_due_giveaways(self) -> None:
        await self.bot.wait_until_ready()

    async def _refresh_finished_message(self, giveaway: dict) -> None:
        guild = self.bot.get_guild(giveaway.get("guild_id"))
        channel = guild.get_channel(giveaway.get("channel_id")) if guild else None
        if not isinstance(channel, discord.TextChannel) or not giveaway.get("message_id"):
            return
        try:
            message = await channel.fetch_message(giveaway["message_id"])
            await message.edit(view=build_finished_giveaway_view(giveaway))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    async def _announce_winners(self, giveaway: dict, winners: list[int], reroll: bool = False) -> None:
        guild = self.bot.get_guild(giveaway.get("guild_id"))
        channel = guild.get_channel(giveaway.get("channel_id")) if guild else None
        if not isinstance(channel, discord.TextChannel):
            return
        prize = giveaway.get("prize", giveaway.get("title", "o prêmio"))
        if winners:
            mentions = ", ".join(f"<@{user_id}>" for user_id in winners)
            heading = "🎉 | Novos ganhadores do sorteio" if reroll else "🎉 | Parabéns aos ganhadores!"
            instructions = (giveaway.get("winner_instructions") or "").strip()
            next_steps = f"\n\n📩 {instructions}" if instructions else ""
            text = f"{heading}\n{mentions} ganharam **{prize}**! 🏆{next_steps}\n\n-# ID do sorteio: `{giveaway['_id']}`"
        else:
            text = f"🏁 O sorteio **{giveaway.get('title', prize)}** terminou sem participantes. Não houve ganhadores.\n\n-# ID: `{giveaway['_id']}`"
        try:
            await channel.send(
                view=build_notice(text, discord.Colour.gold()),
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _dm_winners(self, giveaway: dict, winners: list[int]) -> None:
        instructions = giveaway.get("winner_instructions") or "Entre em contato com a organização para receber as instruções do prêmio."
        text = (
            f"🎉 Você ganhou o sorteio **{giveaway.get('title', 'Sorteio')}**!\n"
            f"🏆 Prêmio: **{giveaway.get('prize', 'Prêmio')}**\n\n{instructions}\n\n"
            f"-# ID do sorteio: `{giveaway['_id']}`"
        )
        for user_id in winners:
            user = self.bot.get_user(user_id)
            if user is None:
                try:
                    user = await self.bot.fetch_user(user_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue
            try:
                await user.send(view=build_notice(text, discord.Colour.gold()))
            except (discord.Forbidden, discord.HTTPException):
                continue


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GiveawayCog(bot))
