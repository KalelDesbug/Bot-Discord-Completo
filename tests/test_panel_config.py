from src.helpers.tickets.panel_config import build_empty_panel, make_panel_key, normalize_panels


def test_new_panel_is_created_without_eros_content_or_categories() -> None:
    panel = build_empty_panel("Meu atendimento")
    assert panel["name"] == "Meu atendimento"
    assert panel["title"] == ""
    assert panel["subtitle"] == ""
    assert panel["welcome"] == ""
    assert panel["image_url"] is None
    assert panel["accent_color"] is None
    assert panel["image_position"] == "inside"
    assert panel["categories"] == []
    assert panel["channel_ids"] == []
    assert panel["created_by_user"] is True


def test_panel_key_is_safe_and_unique() -> None:
    first = make_panel_key("Dúvidas & Suporte", {})
    second = make_panel_key("Dúvidas & Suporte", {first: {}})
    assert first == "duvidas_suporte"
    assert second == "duvidas_suporte_2"
    assert len(second) <= 32


def test_normalize_panels_removes_legacy_eros_presets_only() -> None:
    panels, changed = normalize_panels(
        {
            "suporte": {"title": "Preset antigo"},
            "meu_painel": {"name": "Meu painel", "created_by_user": True, "categories": []},
        }
    )
    assert changed is True
    assert "suporte" not in panels
    assert panels["meu_painel"]["name"] == "Meu painel"
    assert panels["meu_painel"]["title"] == ""
    assert panels["meu_painel"]["categories"] == []


def test_user_can_create_a_panel_named_after_a_legacy_key() -> None:
    panel = build_empty_panel("Suporte")
    panel_key = make_panel_key("Suporte", {})
    panels, changed = normalize_panels({panel_key: panel})

    assert changed is False
    assert panel_key == "suporte"
    assert panels[panel_key]["name"] == "Suporte"
    assert panels[panel_key]["categories"] == []


def test_panel_appearance_settings_are_normalized_and_invalid_values_reset() -> None:
    panels, changed = normalize_panels({
        "meu_painel": {
            "name": "Meu painel",
            "created_by_user": True,
            "accent_color": "#a1b",
            "image_position": "outside",
        }
    })
    assert changed is True
    assert panels["meu_painel"]["accent_color"] == "#AA11BB"
    assert panels["meu_painel"]["image_position"] == "outside"

    panels, changed = normalize_panels({
        "meu_painel": {
            "name": "Meu painel",
            "created_by_user": True,
            "accent_color": "not-a-color",
            "image_position": "center",
        }
    })
    assert changed is True
    assert panels["meu_painel"]["accent_color"] is None
    assert panels["meu_painel"]["image_position"] == "inside"
