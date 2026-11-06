from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_expected_architecture_exists() -> None:
    required = [
        "src/client/client.py",
        "src/config/bot.py",
        "src/config/env.py",
        "src/handlers/commandHandler.py",
        "src/handlers/componentHandler.py",
        "src/handlers/eventHandler.py",
        "src/commands/giveaways.py",
        "src/commands/ticket_painel.py",
        "src/commands/ticket_setup.py",
        "src/commands/welcome.py",
        "src/commands/userinfo.py",
        "src/utils/db/welcome.py",
        "src/helpers/welcome/service.py",
        "src/helpers/welcome/setup_ui.py",
        "src/components/modal/welcome.py",
        "src/components/views/confirmation.py",
        "src/helpers/tickets/panel_setup.py",
        "src/components/buttons",
        "src/components/modal",
        "src/events/channelDelete.py",
        "src/events/interactionCreate.py",
        "src/events/ticketMessages.py",
        "src/events/ready.py",
        "src/helpers/tickets",
        "src/helpers/giveaways",
        "src/utils/importante",
    ]
    assert all((ROOT / item).exists() for item in required)


def test_removed_eros_systems_are_absent() -> None:
    forbidden = [
        "src/commands/cargos.py",
        "src/commands/config_cmd.py",
        "src/commands/config_components.py",
        "src/commands/config_panels.py",
        "src/commands/meta.py",
        "src/commands/metas_geral.py",
        "src/commands/registrar_atividade.py",
        "src/commands/reset_metas.py",
        "src/commands/voice_call.py",
        "src/commands/logs.py",
        "src/events/messageCreate.py",
        "src/events/memberJoin.py",
        "src/events/memberRemove.py",
        "src/events/threadCreate.py",
        "src/events/voiceStateUpdate.py",
        "src/helpers/goals_report.py",
    ]
    assert all(not (ROOT / item).exists() for item in forbidden)
