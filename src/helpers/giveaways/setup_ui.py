from __future__ import annotations

import discord

from src.utils.functions import SafeLayoutView, build_notice
from src.helpers.giveaways.presentation import parse_colour
from src.helpers.giveaways.formatting import format_duration
from src.components.modal.giveaways import SingleFieldModal, GeneralSettingsModal, BonusAmountModal


DEFAULT_DRAFT = {
    "title": "Sorteio da comunidade",
    "description": "Participe clicando no botão abaixo. Boa sorte!",
    "prize": "Prêmio do sorteio",
    "requirement_text": "Sem requisitos",
    "image_url": None,
    "thumbnail_url": None,
    "color": "#5865F2",
    "channel_id": None,
    "duration_seconds": 3600,
    "winners_count": 1,
    "allowed_roles": [],
    "blocked_roles": [],
    "role_bonus": {},
    "bonus_description": "",
    "show_participants": True,
    "announce_winners": True,
    "dm_winners": False,
    "winner_instructions": "Chame a organização na DM para receber as instruções de resgate do prêmio.",
}






class GiveawaySetupView(SafeLayoutView):
    def __init__(self, bot, guild: discord.Guild, owner_id: int, origin_interaction: discord.Interaction, draft: dict | None = None, page: str = "appearance"):
        super().__init__(timeout=900)
        self.bot = bot
        self.guild = guild
        self.owner_id = owner_id
        self.origin_interaction = origin_interaction
        self.draft = {**DEFAULT_DRAFT, **(draft or {})}
        self.draft["role_bonus"] = dict(self.draft.get("role_bonus", {}))
        self.draft["allowed_roles"] = list(self.draft.get("allowed_roles", []))
        self.draft["blocked_roles"] = list(self.draft.get("blocked_roles", []))
        self.page = page
        self.selected_bonus_role_id: int | None = None
        self.render()

    async def owner_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            view=build_notice("❌ Somente a pessoa que abriu este painel pode configurá-lo.", discord.Colour.red()),
            ephemeral=True,
        )
        return False

    def render(self) -> None:
        self.clear_items()
        container = discord.ui.Container(accent_colour=parse_colour(self.draft.get("color")))
        container.add_item(discord.ui.TextDisplay(
            "# 🎉 Configuração de Sorteio\n"
            "Personalize a publicação, defina os requisitos e inicie quando estiver tudo pronto."
        ))
        container.add_item(discord.ui.Separator())

        tabs = [
            ("appearance", "🎨 Aparência"),
            ("general", "⚙️ Geral"),
            ("roles", "🛡️ Cargos permitidos/bloqueados"),
            ("entries", "✨ Entradas extras"),
            ("misc", "🧩 Miscelânea"),
            ("templates", "📚 Templates"),
        ]
        first_tab_row = discord.ui.ActionRow()
        for key, label in tabs[:4]:
            first_tab_row.add_item(SetupTabButton(self, key, label))
        container.add_item(first_tab_row)
        second_tab_row = discord.ui.ActionRow()
        for key, label in tabs[4:]:
            second_tab_row.add_item(SetupTabButton(self, key, label))
        container.add_item(second_tab_row)
        container.add_item(discord.ui.Separator())

        if self.page == "appearance":
            self._render_appearance(container)
        elif self.page == "general":
            self._render_general(container)
        elif self.page == "roles":
            self._render_roles(container)
        elif self.page == "entries":
            self._render_entries(container)
        elif self.page == "misc":
            self._render_misc(container)
        else:
            self._render_templates(container)

        container.add_item(discord.ui.Separator())
        start_row = discord.ui.ActionRow()
        start_row.add_item(StartGiveawayButton(self))
        container.add_item(start_row)
        self.add_item(container)

    def _render_appearance(self, container: discord.ui.Container) -> None:
        lines = [
            "## 🎨 Aparência",
            f"**Nome do sorteio:** {self.draft.get('title') or '—'}",
            f"**Descrição:** {(self.draft.get('description') or '—')[:350]}",
            f"**Imagem da publicação:** {self.draft.get('image_url') or 'Sem imagem'}",
            f"**Thumbnail:** {self.draft.get('thumbnail_url') or 'Sem thumbnail'}",
            f"**Cor:** `{self.draft.get('color', '#5865F2')}`",
        ]
        container.add_item(discord.ui.TextDisplay("\n".join(lines)))
        row = discord.ui.ActionRow(
            SetupActionButton(self, "edit_title", "Nome"),
            SetupActionButton(self, "edit_description", "Descrição"),
            SetupActionButton(self, "edit_image", "Imagem"),
            SetupActionButton(self, "edit_thumbnail", "Thumbnail"),
            SetupActionButton(self, "edit_color", "Cor"),
        )
        container.add_item(row)

    def _render_general(self, container: discord.ui.Container) -> None:
        channel = self.guild.get_channel(self.draft.get("channel_id")) if self.draft.get("channel_id") else None
        duration = format_duration(self.draft.get("duration_seconds", 3600))
        container.add_item(discord.ui.TextDisplay(
            "## ⚙️ Geral\n"
            f"**Canal:** {channel.mention if channel else 'Não selecionado'}\n"
            f"**Prêmio:** {self.draft.get('prize') or '—'}\n"
            f"**Duração:** {duration}\n"
            f"**Quantidade de ganhadores:** {self.draft.get('winners_count', 1)}\n"
            f"**Texto de requisitos:** {self.draft.get('requirement_text') or 'Sem requisitos'}"
        ))
        channel_select = GiveawayChannelSelect(self)
        container.add_item(discord.ui.ActionRow(channel_select))
        container.add_item(discord.ui.ActionRow(
            SetupActionButton(self, "edit_general", "Prêmio, duração e ganhadores"),
            SetupActionButton(self, "edit_requirements", "Texto de requisitos"),
        ))

    def _render_roles(self, container: discord.ui.Container) -> None:
        allowed = self._role_mentions(self.draft.get("allowed_roles", [])) or "Nenhum — todos os membros podem participar"
        blocked = self._role_mentions(self.draft.get("blocked_roles", [])) or "Nenhum cargo bloqueado"
        container.add_item(discord.ui.TextDisplay(
            "## 🛡️ Cargos permitidos/bloqueados\n"
            f"**Permitidos:** {allowed}\n"
            "Quando houver cargos permitidos, a pessoa precisa ter pelo menos um deles.\n\n"
            f"**Bloqueados:** {blocked}\n"
            "Quem tiver qualquer cargo bloqueado não poderá participar."
        ))
        container.add_item(discord.ui.ActionRow(AllowedRolesSelect(self)))
        container.add_item(discord.ui.ActionRow(BlockedRolesSelect(self)))

    def _render_entries(self, container: discord.ui.Container) -> None:
        bonus = self.draft.get("role_bonus", {})
        lines = ["## ✨ Entradas extras por cargo"]
        if bonus:
            for role_id, amount in list(bonus.items())[:15]:
                role = self.guild.get_role(int(role_id))
                label = role.mention if role else f"Cargo removido (`{role_id}`)"
                lines.append(f"• {label}: **+{int(amount)}** entrada(s)")
        else:
            lines.append("Nenhum bônus configurado. Cada participante elegível recebe 1 entrada.")
        selected = self.guild.get_role(self.selected_bonus_role_id) if self.selected_bonus_role_id else None
        if self.draft.get("bonus_description"):
            lines.extend(["", f"**Texto exibido no sorteio:** {self.draft['bonus_description'][:300]}"])
        lines.extend(["", f"**Cargo selecionado:** {selected.mention if selected else 'Selecione abaixo'}"])
        container.add_item(discord.ui.TextDisplay("\n".join(lines)))
        container.add_item(discord.ui.ActionRow(BonusRoleSelect(self)))
        container.add_item(discord.ui.ActionRow(
            SetupActionButton(self, "set_bonus", "Definir entradas extras", style=discord.ButtonStyle.primary),
            SetupActionButton(self, "remove_bonus", "Remover bônus", style=discord.ButtonStyle.danger),
            SetupActionButton(self, "edit_bonus_description", "Texto do bônus"),
        ))

    def _render_misc(self, container: discord.ui.Container) -> None:
        container.add_item(discord.ui.TextDisplay(
            "## 🧩 Miscelânea\n"
            f"**Mostrar botão de participantes:** {'Sim' if self.draft.get('show_participants', True) else 'Não'}\n"
            f"**Anunciar vencedores no canal:** {'Sim' if self.draft.get('announce_winners', True) else 'Não'}\n"
            f"**Enviar instruções por DM:** {'Sim' if self.draft.get('dm_winners', False) else 'Não'}\n\n"
            f"**Instruções do prêmio:** {self.draft.get('winner_instructions') or 'Não configuradas'}"
        ))
        container.add_item(discord.ui.ActionRow(
            SetupActionButton(self, "toggle_participants", "Alternar participantes"),
            SetupActionButton(self, "toggle_announcement", "Alternar anúncio"),
            SetupActionButton(self, "toggle_dm", "Alternar DM"),
        ))
        container.add_item(discord.ui.ActionRow(SetupActionButton(self, "edit_winner_instructions", "Editar instruções do prêmio")))

    def _render_templates(self, container: discord.ui.Container) -> None:
        container.add_item(discord.ui.TextDisplay(
            "## 📚 Templates\n"
            "Aplique um modelo visual pronto. Isso altera nome, descrição e cor; os demais campos são preservados."
        ))
        container.add_item(discord.ui.ActionRow(
            SetupActionButton(self, "template_classic", "Clássico", style=discord.ButtonStyle.secondary),
            SetupActionButton(self, "template_clean", "Clean", style=discord.ButtonStyle.secondary),
            SetupActionButton(self, "template_elegant", "Elegante", style=discord.ButtonStyle.secondary),
        ))

    def _role_mentions(self, role_ids: list[int]) -> str:
        values = []
        for role_id in role_ids[:20]:
            role = self.guild.get_role(int(role_id))
            values.append(role.mention if role else f"`{role_id}`")
        return ", ".join(values)

    async def change_page(self, interaction: discord.Interaction, page: str) -> None:
        if not await self.owner_check(interaction):
            return
        self.page = page
        self.render()
        await interaction.response.edit_message(view=self)

    async def handle_action(self, interaction: discord.Interaction, action: str) -> None:
        if not await self.owner_check(interaction):
            return

        if action.startswith("edit_"):
            field_map = {
                "edit_title": ("title", "Nome do sorteio", "Dê um nome para o sorteio.", 200, False),
                "edit_description": ("description", "Descrição do sorteio", "Escreva a descrição que aparecerá na publicação.", 2000, True),
                "edit_image": ("image_url", "URL da imagem", "URL HTTPS da imagem principal. Deixe vazio para remover.", 500, False),
                "edit_thumbnail": ("thumbnail_url", "URL da thumbnail", "URL HTTPS da thumbnail. Deixe vazio para remover.", 500, False),
                "edit_color": ("color", "Cor hexadecimal", "Use uma cor como #5865F2.", 7, False),
                "edit_requirements": ("requirement_text", "Texto de requisitos", "Texto que será mostrado aos participantes.", 300, False),
                "edit_winner_instructions": ("winner_instructions", "Instruções do prêmio", "Mensagem enviada aos ganhadores se a opção de DM estiver ativada.", 1000, True),
                "edit_bonus_description": ("bonus_description", "Texto das entradas extras", "Explique as tarefas ou condições para receber entradas extras. Entradas de tarefas podem ser concedidas com /giveaway entrada-extra.", 800, True),
            }
            if action == "edit_general":
                await interaction.response.send_modal(GeneralSettingsModal(self))
                return
            key, label, placeholder, max_length, paragraph = field_map[action]
            await interaction.response.send_modal(SingleFieldModal(self, key, label, placeholder, max_length, paragraph))
            return

        if action == "set_bonus":
            if not self.selected_bonus_role_id:
                await interaction.response.send_message(view=build_notice("Selecione um cargo antes de configurar o bônus.", discord.Colour.orange()), ephemeral=True)
                return
            await interaction.response.send_modal(BonusAmountModal(self, self.selected_bonus_role_id))
            return

        if action == "remove_bonus":
            if not self.selected_bonus_role_id:
                await interaction.response.send_message(view=build_notice("Selecione um cargo antes de remover um bônus.", discord.Colour.orange()), ephemeral=True)
                return
            self.draft["role_bonus"].pop(str(self.selected_bonus_role_id), None)
            self.draft["role_bonus"].pop(self.selected_bonus_role_id, None)
            self.render()
            await interaction.response.edit_message(view=self)
            return

        if action == "toggle_participants":
            self.draft["show_participants"] = not self.draft.get("show_participants", True)
        elif action == "toggle_announcement":
            self.draft["announce_winners"] = not self.draft.get("announce_winners", True)
        elif action == "toggle_dm":
            self.draft["dm_winners"] = not self.draft.get("dm_winners", False)
        elif action == "template_classic":
            self.draft.update({"title": "🎉 Sorteio especial!", "description": "Participe e concorra ao prêmio. Boa sorte a todos!", "color": "#5865F2"})
        elif action == "template_clean":
            self.draft.update({"title": "Sorteio", "description": "Clique em Participar para entrar no sorteio.", "color": "#2B2D31"})
        elif action == "template_elegant":
            self.draft.update({"title": "✨ Sorteio especial", "description": "Um presente especial para a comunidade. Boa sorte!", "color": "#DDA0DD"})

        self.render()
        await interaction.response.edit_message(view=self)

    async def sync_after_modal(self, interaction: discord.Interaction) -> None:
        try:
            await self.origin_interaction.edit_original_response(view=self)
        except (discord.HTTPException, discord.NotFound):
            await interaction.followup.send(
                view=build_notice("✅ Configuração atualizada. Reabra `/giveaway setup` caso este painel tenha expirado.", discord.Colour.green()),
                ephemeral=True,
            )


class SetupTabButton(discord.ui.Button):
    def __init__(self, setup_view: GiveawaySetupView, page: str, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary if setup_view.page == page else discord.ButtonStyle.secondary)
        self.setup_view = setup_view
        self.page = page

    async def callback(self, interaction: discord.Interaction):
        await self.setup_view.change_page(interaction, self.page)


class SetupActionButton(discord.ui.Button):
    def __init__(self, setup_view: GiveawaySetupView, action: str, label: str, style: discord.ButtonStyle = discord.ButtonStyle.secondary):
        super().__init__(label=label, style=style)
        self.setup_view = setup_view
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        await self.setup_view.handle_action(interaction, self.action)


class StartGiveawayButton(discord.ui.Button):
    def __init__(self, setup_view: GiveawaySetupView):
        super().__init__(label="Iniciar Sorteio", emoji="🎉", style=discord.ButtonStyle.success)
        self.setup_view = setup_view

    async def callback(self, interaction: discord.Interaction):
        if not await self.setup_view.owner_check(interaction):
            return
        cog = interaction.client.get_cog("GiveawayCog")
        if cog is None:
            await interaction.response.send_message(view=build_notice("❌ O sistema de sorteios está indisponível no momento.", discord.Colour.red()), ephemeral=True)
            return
        await cog.create_from_setup(interaction, self.setup_view)


class GiveawayChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, setup_view: GiveawaySetupView):
        super().__init__(placeholder="Selecione o canal onde o sorteio será publicado", channel_types=[discord.ChannelType.text], min_values=1, max_values=1)
        self.setup_view = setup_view

    async def callback(self, interaction: discord.Interaction):
        if not await self.setup_view.owner_check(interaction):
            return
        self.setup_view.draft["channel_id"] = self.values[0].id
        self.setup_view.render()
        await interaction.response.edit_message(view=self.setup_view)


class AllowedRolesSelect(discord.ui.RoleSelect):
    def __init__(self, setup_view: GiveawaySetupView):
        super().__init__(placeholder="Cargos permitidos (vazio = qualquer membro)", min_values=0, max_values=25)
        self.setup_view = setup_view

    async def callback(self, interaction: discord.Interaction):
        if not await self.setup_view.owner_check(interaction):
            return
        self.setup_view.draft["allowed_roles"] = [role.id for role in self.values]
        self.setup_view.render()
        await interaction.response.edit_message(view=self.setup_view)


class BlockedRolesSelect(discord.ui.RoleSelect):
    def __init__(self, setup_view: GiveawaySetupView):
        super().__init__(placeholder="Cargos bloqueados (opcional)", min_values=0, max_values=25)
        self.setup_view = setup_view

    async def callback(self, interaction: discord.Interaction):
        if not await self.setup_view.owner_check(interaction):
            return
        self.setup_view.draft["blocked_roles"] = [role.id for role in self.values]
        self.setup_view.render()
        await interaction.response.edit_message(view=self.setup_view)


class BonusRoleSelect(discord.ui.RoleSelect):
    def __init__(self, setup_view: GiveawaySetupView):
        super().__init__(placeholder="Selecione o cargo que receberá entradas extras", min_values=1, max_values=1)
        self.setup_view = setup_view

    async def callback(self, interaction: discord.Interaction):
        if not await self.setup_view.owner_check(interaction):
            return
        self.setup_view.selected_bonus_role_id = self.values[0].id
        self.setup_view.render()
        await interaction.response.edit_message(view=self.setup_view)
