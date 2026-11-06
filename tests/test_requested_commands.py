from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _app_command_names(relative_path: str) -> set[str]:
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            function = decorator.func
            if not (
                isinstance(function, ast.Attribute)
                and function.attr == "command"
                and isinstance(function.value, ast.Name)
                and function.value.id == "app_commands"
            ):
                continue
            for keyword in decorator.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    if isinstance(keyword.value.value, str):
                        names.add(keyword.value.value)
    return names


def test_welcome_has_one_unified_setup_command() -> None:
    assert _app_command_names("src/commands/welcome.py") == {"welcome-setup"}


def test_welcome_setup_panel_contains_all_controls() -> None:
    source = (ROOT / "src/helpers/welcome/setup_ui.py").read_text(encoding="utf-8")
    assert "class WelcomeSetupView" in source
    assert "class WelcomeChannelSelect" in source
    modal_source = (ROOT / "src/components/modal/welcome.py").read_text(encoding="utf-8")
    assert "WelcomeMessageModal" in source
    assert "class WelcomeMessageModal" in modal_source
    assert '"enable"' in source
    assert '"disable"' in source
    assert '"preview"' in source
    assert "welcome_image_url" in source
    assert "welcome_message" in source
    assert "WelcomeAppearanceView" in source
    assert "WelcomeImagePositionSelect" in source
    assert "welcome_accent_color" in source


def test_requested_userinfo_and_moderation_commands_are_registered() -> None:
    assert _app_command_names("src/commands/userinfo.py") == {"userinfo"}
    assert _app_command_names("src/commands/moderation.py") == {
        "ban",
        "kick",
        "mute",
    }


def test_ticket_panel_appearance_is_configurable() -> None:
    source = (ROOT / "src/helpers/tickets/panel_setup.py").read_text(encoding="utf-8")
    view_source = (ROOT / "src/components/buttons/ticket_panels.py").read_text(encoding="utf-8")
    assert "PanelAppearanceView" in source
    assert "PanelAccentColorModal" in source
    assert "PanelImagePositionSelect" in source
    assert 'value="aparencia"' in source
    assert 'panel.get("accent_color")' in view_source
    assert 'panel.get("image_position"' in view_source
    ticket_core = (ROOT / "src/helpers/tickets/ticket_core.py").read_text(encoding="utf-8")
    admin_view = (ROOT / "src/components/buttons/ticket_actions.py").read_text(encoding="utf-8")
    assert '"accent_color": accent_color' in ticket_core
    assert 'accent_color=ticket.get("accent_color")' in ticket_core
    assert "discord_colour(accent_color)" in admin_view


def test_welcome_appearance_is_saved_and_used_in_delivery() -> None:
    setup_source = (ROOT / "src/helpers/welcome/setup_ui.py").read_text(encoding="utf-8")
    modal_source = (ROOT / "src/components/modal/welcome.py").read_text(encoding="utf-8")
    service_source = (ROOT / "src/helpers/welcome/service.py").read_text(encoding="utf-8")
    welcome_repository = (ROOT / "src/utils/db/welcome.py").read_text(encoding="utf-8")
    assert "welcome_accent_color" in setup_source
    assert "welcome_image_position" in setup_source
    assert "WelcomeAccentColorModal" in modal_source
    assert "image_position" in service_source
    assert "accent_color" in service_source
    assert '"welcome_accent_color"' in welcome_repository
    assert '"welcome_image_position"' in welcome_repository
