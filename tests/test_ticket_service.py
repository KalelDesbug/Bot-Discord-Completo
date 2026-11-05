from types import SimpleNamespace

from src.bot_app.features.tickets.service import TicketService
from src.bot_app.features.welcome.service import WelcomeService


def test_channel_name_replaces_invalid_characters() -> None:
    name = TicketService.channel_name("João Silva!", 123)
    assert name.startswith("ticket-")
    assert all(character.isalnum() or character == "-" for character in name)


def test_channel_name_uses_user_id_when_name_is_empty() -> None:
    name = TicketService.channel_name("!!!", 456)
    assert name == "ticket-456"


def test_can_close_owner_or_support_role() -> None:
    owner_member = SimpleNamespace(id=15, roles=[SimpleNamespace(id=1)])
    support_member = SimpleNamespace(id=99, roles=[SimpleNamespace(id=77)])
    other_member = SimpleNamespace(id=88, roles=[SimpleNamespace(id=1)])

    assert TicketService.can_close(owner_member, 15, None) is True
    assert TicketService.can_close(support_member, 15, 77) is True
    assert TicketService.can_close(other_member, 15, 77) is False


def test_render_welcome_message() -> None:
    member = SimpleNamespace(
        mention="<@123>", guild=SimpleNamespace(name="Guild Test")
    )
    message = WelcomeService.render("{member} bem-vindo ao {server}!", member)
    assert message == "<@123> bem-vindo ao Guild Test!"
