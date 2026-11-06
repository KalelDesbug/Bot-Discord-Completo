from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.utils.database import Database


@pytest.mark.asyncio
async def test_database_creates_schema_and_persists_across_reopen(tmp_path) -> None:
    path = tmp_path / "data" / "bot.sqlite3"
    db = Database(path)
    await db.create_indexes()

    config = await db.get_config(123)
    assert config["_id"] == 123
    await db.update_config(123, {"ticket_staff_role_ids": [10, 20]})
    from src.helpers.tickets.panel_config import build_empty_panel
    panel = build_empty_panel("Atendimento")
    panel["accent_color"] = "#5865F2"
    panel["image_position"] = "outside"
    await db.update_config(123, {"ticket_panels": {"atendimento": panel}})
    await db.update_welcome_settings(
        123,
        {
            "welcome_channel_id": 456,
            "welcome_enabled": True,
            "welcome_message": "Olá, {member}!",
            "welcome_accent_color": "#12abef",
            "welcome_image_position": "inside",
        },
    )
    await db.close()

    reopened = Database(path)
    await reopened.create_indexes()
    reopened_config = await reopened.get_config(123)
    assert reopened_config["ticket_staff_role_ids"] == [10, 20]
    stored_panel = reopened_config["ticket_panels"]["atendimento"]
    assert stored_panel["accent_color"] == "#5865F2"
    assert stored_panel["image_position"] == "outside"
    welcome = await reopened.get_welcome_settings(123)
    assert welcome["welcome_channel_id"] == 456
    assert welcome["welcome_enabled"] is True
    assert welcome["welcome_message"] == "Olá, {member}!"
    assert welcome["welcome_accent_color"] == "#12ABEF"
    assert welcome["welcome_image_position"] == "inside"
    await reopened.close()


@pytest.mark.asyncio
async def test_ticket_numbers_are_atomic_under_concurrent_calls(tmp_path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.create_indexes()

    values = await asyncio.gather(*(db.next_ticket_number(987) for _ in range(40)))

    assert sorted(values) == list(range(1, 41))
    await db.close()


@pytest.mark.asyncio
async def test_document_updates_nested_operators_and_queries(tmp_path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.create_indexes()
    now = datetime.now(timezone.utc)
    giveaway = {
        "_id": "giveaway-1",
        "guild_id": 123,
        "status": "active",
        "ends_at": now + timedelta(minutes=5),
        "participants": {},
        "participant_count": 0,
        "total_entries": 0,
    }
    await db.create_giveaway(giveaway)

    joins = await asyncio.gather(
        *(db.join_giveaway("giveaway-1", 555, 3, now) for _ in range(12))
    )
    assert sum(joins) == 1
    assert await db.add_giveaway_entries("giveaway-1", 555, 2, 999, "teste", now)

    stored = await db.get_giveaway("giveaway-1")
    assert stored is not None
    assert "participants" not in stored
    assert stored["participant_count"] == 1
    assert stored["total_entries"] == 5
    participant = await db.get_giveaway_participant("giveaway-1", 555)
    assert participant is not None
    assert participant["entries"] == 5
    assert participant["joined_at"] == now.isoformat()
    bonus_log = await db.get_giveaway_bonus_log("giveaway-1", 555)
    assert bonus_log[0]["awarded_at"] == now.isoformat()
    selected = await db.select_giveaway_winners("giveaway-1", 1)
    assert selected == [{"user_id": "555", "entries": 5}]

    assert not await db.claim_giveaway_end("giveaway-1", now=now)
    assert await db.claim_giveaway_end("giveaway-1", force=True, now=now)
    assert not await db.claim_giveaway_end("giveaway-1", force=True, now=now)
    await db.close()


@pytest.mark.asyncio
async def test_ticket_query_cursor_projection_and_delete(tmp_path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.create_indexes()
    for number in range(1, 4):
        await db.tickets.insert_one({
            "_id": str(number),
            "guild_id": 123,
            "owner_id": 456,
            "panel": "registro" if number == 2 else "suporte",
            "status": "fechado" if number == 3 else "aberto",
            "number": number,
            "added_members": [],
        })

    doc = await db.tickets.find_one(
        {"guild_id": 123, "owner_id": 456, "panel": "suporte", "status": "aberto"},
        {"number": 1, "owner_id": 1},
    )
    assert doc is not None
    assert set(doc) == {"_id", "number", "owner_id"}

    cursor = db.tickets.find({"guild_id": 123}).sort("number", -1).limit(2)
    recent = [item async for item in cursor]
    assert [item["number"] for item in recent] == [3, 2]

    await db.tickets.update_one({"_id": "1"}, {"$addToSet": {"added_members": 777}})
    await db.tickets.update_one({"_id": "1"}, {"$addToSet": {"added_members": 777}})
    await db.tickets.update_one({"_id": "1"}, {"$pull": {"added_members": 777}})
    updated = await db.tickets.find_one({"_id": "1"})
    assert updated["added_members"] == []

    result = await db.tickets.delete_one({"_id": "3"})
    assert result.deleted_count == 1
    assert await db.tickets.find_one({"_id": "3"}) is None
    await db.close()


@pytest.mark.asyncio
async def test_due_giveaways_supports_datetime_operators(tmp_path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.create_indexes()
    now = datetime.now(timezone.utc)
    await db.create_giveaway({
        "_id": "due",
        "guild_id": 12,
        "status": "active",
        "ends_at": now - timedelta(seconds=1),
        "participants": {},
    })
    await db.create_giveaway({
        "_id": "future",
        "guild_id": 12,
        "status": "active",
        "ends_at": now + timedelta(hours=1),
        "participants": {},
    })

    due = await db.due_giveaways(now)
    assert [item["_id"] for item in due] == ["due"]
    assert isinstance(due[0]["ends_at"], datetime)
    await db.close()


@pytest.mark.asyncio
async def test_concurrent_config_initialization_is_race_safe(tmp_path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.create_indexes()

    results = await asyncio.gather(*(db.get_config(4321) for _ in range(32)))

    assert all(result["_id"] == 4321 for result in results)
    assert await db.config.find_one({"_id": 4321}) is not None
    await db.close()


@pytest.mark.asyncio
async def test_open_tickets_are_unique_per_user_and_panel(tmp_path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.create_indexes()
    first = {
        "_id": "ticket-a",
        "guild_id": 123,
        "owner_id": 456,
        "panel": "suporte",
        "status": "aberto",
        "number": 1,
    }
    await db.tickets.insert_one(first)

    with pytest.raises(ValueError, match="Documento duplicado"):
        await db.tickets.insert_one({**first, "_id": "ticket-b", "number": 2})

    await db.tickets.insert_one({**first, "_id": "ticket-c", "panel": "registro", "number": 3})
    await db.tickets.insert_one({**first, "_id": "ticket-d", "status": "fechado", "number": 4})
    await db.close()


@pytest.mark.asyncio
async def test_config_starts_empty_and_removes_legacy_eros_ticket_presets(tmp_path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.create_indexes()

    await db.config.insert_one({
        "_id": 654,
        "ticket_category_id": None,
        "ticket_staff_role_ids": [],
        "ticket_log_channel_id": None,
        "ticket_panels": {
            "suporte": {"title": "Eros preset", "categories": [{"label": "Dúvidas"}]},
            "my_custom_panel": {
                "name": "Meu painel",
                "title": "Meu título",
                "categories": [{"label": "Ajuda"}],
                "created_by_user": True,
            },
        },
    })

    config = await db.get_config(654)
    assert set(config["ticket_panels"]) == {"my_custom_panel"}
    assert config["ticket_panels"]["my_custom_panel"]["title"] == "Meu título"

    empty_config = await db.get_config(655)
    assert empty_config["ticket_panels"] == {}
    await db.close()


@pytest.mark.asyncio
async def test_ticket_messages_are_persisted_and_read_in_bounded_pages(tmp_path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.create_indexes()
    records = [
        {
            "channel_id": 900,
            "message_id": 1000 + index,
            "guild_id": 123,
            "author_id": 500 + index,
            "author_name": f"User {index}",
            "content": f"Mensagem {index}",
            "created_at": f"2026-11-06T12:00:{index:02d}+00:00",
            "attachments": [],
        }
        for index in range(5)
    ]
    await db.save_ticket_messages(records)
    assert await db.ticket_history_cursor(900) is None
    await db.save_ticket_messages(records[:3], update_history_cursor=True)
    await db.save_ticket_messages([{**records[2], "content": "Mensagem editada"}])

    assert await db.latest_ticket_message_id(900) == 1004
    assert await db.ticket_history_cursor(900) == 1002
    first_page = await db.get_ticket_message_page(900, limit=2)
    second_page = await db.get_ticket_message_page(900, after_message_id=first_page[-1]["message_id"], limit=2)
    third_page = await db.get_ticket_message_page(900, after_message_id=second_page[-1]["message_id"], limit=2)

    assert [item["message_id"] for item in first_page] == [1000, 1001]
    assert [item["message_id"] for item in second_page] == [1002, 1003]
    assert second_page[0]["content"] == "Mensagem editada"
    assert [item["message_id"] for item in third_page] == [1004]

    await db.delete_ticket_messages(900, [1001, 1003])
    remaining = await db.get_ticket_message_page(900, limit=10)
    assert [item["message_id"] for item in remaining] == [1000, 1002, 1004]
    await db.close()


@pytest.mark.asyncio
async def test_legacy_giveaway_participants_are_migrated_to_normalized_table(tmp_path) -> None:
    path = tmp_path / "bot.sqlite3"
    db = Database(path)
    await db.create_indexes()
    now = datetime.now(timezone.utc)
    await db.giveaways.insert_one({
        "_id": "legacy-giveaway",
        "guild_id": 123,
        "status": "ended",
        "participants": {
            "10": {
                "entries": 3,
                "joined_at": now,
                "bonus_log": [{
                    "amount": 2,
                    "awarded_by": 99,
                    "reason": "Migração",
                    "awarded_at": now,
                }],
            },
            "20": {"entries": 1, "joined_at": now, "bonus_log": []},
        },
        "participant_count": 2,
        "total_entries": 4,
        "winners": [10],
    })
    await db._run_locked(lambda: db.connection.execute("PRAGMA user_version = 1"))
    await db.close()

    reopened = Database(path)
    await reopened.create_indexes()
    migrated = await reopened.get_giveaway("legacy-giveaway")
    assert migrated is not None
    assert "participants" not in migrated
    assert migrated["winner_entries"] == {"10": 3}
    assert migrated["participant_count"] == 2
    assert migrated["total_entries"] == 4
    assert (await reopened.get_giveaway_participant("legacy-giveaway", 10))["entries"] == 3
    migrated_bonus = await reopened.get_giveaway_bonus_log("legacy-giveaway", 10)
    assert migrated_bonus[0]["awarded_at"] == now.isoformat()
    assert migrated_bonus[0]["reason"] == "Migração"
    await reopened.close()


@pytest.mark.asyncio
async def test_giveaway_participants_are_paged_and_winners_are_unique(tmp_path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.create_indexes()
    now = datetime.now(timezone.utc)
    await db.create_giveaway({
        "_id": "large-giveaway",
        "guild_id": 123,
        "status": "active",
        "ends_at": now + timedelta(hours=1),
        "participant_count": 0,
        "total_entries": 0,
    })

    joins = await asyncio.gather(*(
        db.join_giveaway("large-giveaway", user_id, 1 + user_id % 3, now)
        for user_id in range(1, 301)
    ))
    assert all(joins)
    first_page = await db.get_giveaway_participants_page("large-giveaway", limit=25)
    second_page = await db.get_giveaway_participants_page("large-giveaway", limit=25, offset=25)
    assert len(first_page) == len(second_page) == 25
    assert first_page[0]["user_id"] != second_page[0]["user_id"]

    winners = await db.select_giveaway_winners("large-giveaway", 10)
    assert len(winners) == 10
    assert len({item["user_id"] for item in winners}) == 10
    assert all(item["entries"] in {1, 2, 3} for item in winners)
    doc = await db.get_giveaway("large-giveaway")
    assert doc["participant_count"] == 300
    assert doc["total_entries"] == sum(1 + user_id % 3 for user_id in range(1, 301))
    assert "participants" not in doc
    await db.close()


@pytest.mark.asyncio
async def test_due_giveaways_limit_bounds_loaded_documents(tmp_path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.create_indexes()
    now = datetime.now(timezone.utc)
    for index in range(5):
        await db.create_giveaway({
            "_id": f"due-{index}",
            "guild_id": 12,
            "status": "active",
            "ends_at": now - timedelta(seconds=index + 1),
        })

    due = await db.due_giveaways(now, limit=2)
    assert len(due) == 2
    await db.close()
