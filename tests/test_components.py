import asyncio
from unittest.mock import AsyncMock

from src.bot_app.features.moderation.confirmation import ConfirmationLayout
from src.bot_app.features.tickets.components import TicketControls, TicketPanel


def test_ticket_views_are_persistent_components_v2() -> None:
    panel = TicketPanel()
    controls = TicketControls()

    assert panel.has_components_v2()
    assert controls.has_components_v2()
    assert panel.is_persistent()
    assert controls.is_persistent()
    assert {
        item.custom_id for item in panel.walk_children() if hasattr(item, "custom_id")
    } == {"tickets:open"}
    assert {
        item.custom_id for item in controls.walk_children() if hasattr(item, "custom_id")
    } == {"tickets:close"}


def test_confirmation_action_runs_at_most_once() -> None:
    async def run() -> None:
        action = AsyncMock(return_value="Concluído.")
        source_interaction = type(
            "SourceInteraction",
            (),
            {
                "user": type("User", (), {"id": 123})(),
                "edit_original_response": AsyncMock(),
            },
        )()
        view = ConfirmationLayout(source_interaction, "Confirmar ação?", action)
        assert view.has_components_v2()
        assert len(view.to_components()) == 1
        interaction = type(
            "Interaction",
            (),
            {
                "response": type(
                    "Response",
                    (),
                    {
                        "defer": AsyncMock(),
                        "send_message": AsyncMock(),
                    },
                )(),
                "message": type("Message", (), {"edit": AsyncMock()})(),
                "followup": type(
                    "Followup", (), {"send": AsyncMock()}
                )(),
            },
        )()

        await view.confirm(interaction)
        await view.confirm(interaction)

        action.assert_awaited_once()
        interaction.response.defer.assert_awaited_once()
        interaction.message.edit.assert_awaited_once_with(view=None)
        interaction.response.send_message.assert_awaited_once()

    asyncio.run(run())


def test_timed_out_confirmation_cannot_run_action() -> None:
    async def run() -> None:
        action = AsyncMock(return_value="Concluído.")
        source_interaction = type(
            "SourceInteraction",
            (),
            {
                "user": type("User", (), {"id": 123})(),
                "edit_original_response": AsyncMock(),
            },
        )()
        view = ConfirmationLayout(source_interaction, "Confirmar ação?", action)

        await view.on_timeout()

        assert view._completed
        assert all(button.disabled for button in view._buttons)
        source_interaction.edit_original_response.assert_awaited_once_with(view=view)
        action.assert_not_awaited()

    asyncio.run(run())
