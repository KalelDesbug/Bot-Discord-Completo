import discord


class WelcomeService:
    @staticmethod
    def render(template: str, member: discord.Member) -> str:
        return template.replace("{member}", member.mention).replace(
            "{server}", member.guild.name
        )
