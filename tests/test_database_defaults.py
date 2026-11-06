from src.utils.database_defaults import default_config, default_ticket_panels


def test_default_config_starts_without_prebuilt_ticket_panels() -> None:
    config = default_config(123)
    assert set(config) == {
        "_id",
        "ticket_category_id",
        "ticket_staff_role_ids",
        "ticket_log_channel_id",
        "ticket_panels",
    }
    assert config["ticket_panels"] == {}


def test_default_ticket_panels_returns_independent_empty_values() -> None:
    first = default_ticket_panels()
    second = default_ticket_panels()
    first["custom"] = {"name": "Meu painel"}
    assert second == {}
