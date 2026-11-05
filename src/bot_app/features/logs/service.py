from enum import Enum

import discord


class LogLevel(Enum):
    STARTUP = ("⚪", discord.Colour.from_rgb(255, 255, 255))
    INFO = ("🔵", discord.Colour.blue())
    SUCCESS = ("🟢", discord.Colour.green())
    WARNING = ("🟡", discord.Colour.gold())
    ERROR = ("🔴", discord.Colour.red())
    RESTART = ("🟣", discord.Colour.purple())

    @property
    def icon(self) -> str:
        return self.value[0]

    @property
    def colour(self) -> discord.Colour:
        return self.value[1]


def build_log_embed(title: str, message: str, level: LogLevel = LogLevel.INFO) -> discord.Embed:
    safe_title = (title.strip() or "Registro do bot")[:250]
    safe_message = (message.strip() or "Sem detalhes adicionais.")[:3500]
    return discord.Embed(
        title=f"{level.icon} {safe_title}"[:256],
        description=safe_message,
        colour=level.colour,
        timestamp=discord.utils.utcnow(),
    )


def friendly_error(error: BaseException) -> str:
    if isinstance(error, discord.Forbidden):
        return "O Discord recusou a ação por falta de permissão. Confira as permissões e os cargos do bot."
    if isinstance(error, discord.NotFound):
        return "O item solicitado não existe mais ou foi removido."
    if isinstance(error, discord.HTTPException):
        return "O Discord não conseguiu concluir a solicitação. Aguarde um pouco e tente novamente."
    return "Ocorreu uma falha inesperada. Tente novamente; os detalhes técnicos foram registrados no console do bot."
