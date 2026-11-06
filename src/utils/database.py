from __future__ import annotations

import asyncio
import json
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Callable, TypeVar


from src.utils.database_defaults import (
    default_config,
    default_ticket_panels,
)
from src.utils.db.config import ConfigRepository
from src.utils.db.giveaways import GiveawayRepository
from src.utils.db.tickets import TicketRepository
from src.utils.db.welcome import WelcomeRepository

logger = logging.getLogger("discord.database")
_Result = TypeVar("_Result")


def _encode_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, dict):
        return {str(key): _encode_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Tipo não serializável no banco SQLite: {type(value).__name__}")


def _decode_value(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"__datetime__"}:
            return datetime.fromisoformat(value["__datetime__"])
        return {key: _decode_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode_value(item) for item in value]
    return value


def _serialize(document: dict[str, Any]) -> str:
    return json.dumps(_encode_value(document), ensure_ascii=False, separators=(",", ":"))


def _deserialize(raw: str) -> dict[str, Any]:
    return _decode_value(json.loads(raw))


def _get_path(document: dict[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = document
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _set_path(document: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = document
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def _unset_path(document: dict[str, Any], path: str) -> None:
    parts = path.split(".")
    current: Any = document
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return
        current = current.get(part)
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def _comparable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.timestamp()
    return value


def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for field, expected in query.items():
        if field == "$or":
            if not isinstance(expected, list) or not any(_matches(document, item) for item in expected):
                return False
            continue
        if field == "$and":
            if not isinstance(expected, list) or not all(_matches(document, item) for item in expected):
                return False
            continue

        exists, actual = _get_path(document, field)
        if isinstance(expected, dict) and any(str(key).startswith("$") for key in expected):
            for operator, operand in expected.items():
                if operator == "$exists":
                    if exists is not bool(operand):
                        return False
                elif operator == "$lte":
                    if not exists or _comparable(actual) > _comparable(operand):
                        return False
                elif operator == "$lt":
                    if not exists or _comparable(actual) >= _comparable(operand):
                        return False
                elif operator == "$gte":
                    if not exists or _comparable(actual) < _comparable(operand):
                        return False
                elif operator == "$gt":
                    if not exists or _comparable(actual) <= _comparable(operand):
                        return False
                elif operator == "$ne":
                    if exists and actual == operand:
                        return False
                elif operator == "$in":
                    if not exists or actual not in operand:
                        return False
                elif operator == "$nin":
                    if exists and actual in operand:
                        return False
                else:
                    raise NotImplementedError(f"Operador de consulta SQLite não suportado: {operator}")
        elif not exists or actual != expected:
            return False
    return True


def _apply_update(document: dict[str, Any], update: dict[str, Any]) -> None:
    if not update:
        return
    if not any(str(key).startswith("$") for key in update):
        replacement = dict(update)
        replacement.setdefault("_id", document.get("_id"))
        document.clear()
        document.update(replacement)
        return

    for field, value in update.get("$set", {}).items():
        _set_path(document, field, value)
    for field, value in update.get("$inc", {}).items():
        exists, current = _get_path(document, field)
        _set_path(document, field, (current if exists else 0) + value)
    for field, value in update.get("$push", {}).items():
        exists, current = _get_path(document, field)
        if not exists or not isinstance(current, list):
            current = []
        current.append(value)
        _set_path(document, field, current)
    for field, value in update.get("$addToSet", {}).items():
        exists, current = _get_path(document, field)
        if not exists or not isinstance(current, list):
            current = []
        if value not in current:
            current.append(value)
        _set_path(document, field, current)
    for field, value in update.get("$pull", {}).items():
        exists, current = _get_path(document, field)
        if exists and isinstance(current, list):
            _set_path(document, field, [item for item in current if item != value])
    for field in update.get("$unset", {}):
        _unset_path(document, field)


@dataclass(slots=True)
class UpdateResult:
    matched_count: int = 0
    modified_count: int = 0


@dataclass(slots=True)
class DeleteResult:
    deleted_count: int = 0


class SQLiteCursor:
    def __init__(self, collection: "SQLiteCollection", query: dict[str, Any]) -> None:
        self.collection = collection
        self.query = query
        self._sort_field: str | None = None
        self._sort_direction = 1
        self._limit: int | None = None

    def sort(self, key: str | list[tuple[str, int]], direction: int = 1) -> "SQLiteCursor":
        if isinstance(key, list):
            if key:
                self._sort_field, self._sort_direction = key[0]
        else:
            self._sort_field = key
            self._sort_direction = -1 if direction < 0 else 1
        return self

    def limit(self, count: int) -> "SQLiteCursor":
        self._limit = max(0, int(count))
        return self

    async def _load(self) -> list[dict[str, Any]]:
        return await self.collection._find_many(
            self.query,
            sort_field=self._sort_field,
            sort_direction=self._sort_direction,
            limit=self._limit,
        )

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[dict[str, Any]]:
        for document in await self._load():
            yield document


class SQLiteCollection:
    """Subset seguro da API de documentos usado internamente pelo projeto."""

    def __init__(self, database: "Database", name: str) -> None:
        self.database = database
        self.name = name

    async def find_one(
        self, query: dict[str, Any], projection: dict[str, int] | None = None
    ) -> dict[str, Any] | None:
        documents = await self._find_many(query, limit=1)
        if not documents:
            return None
        document = documents[0]
        if projection:
            selected = {key for key, enabled in projection.items() if enabled}
            if selected:
                selected.add("_id")
                document = {key: value for key, value in document.items() if key in selected}
        return document

    def find(self, query: dict[str, Any] | None = None) -> SQLiteCursor:
        return SQLiteCursor(self, query or {})

    async def insert_one(self, document: dict[str, Any]) -> None:
        if not isinstance(document, dict) or "_id" not in document:
            raise ValueError("Todo documento SQLite precisa de _id.")
        await self.database._insert_document(self.name, document)

    async def update_one(
        self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False
    ) -> UpdateResult:
        return await self.database._update_document(self.name, query, update, upsert)

    async def delete_one(self, query: dict[str, Any]) -> DeleteResult:
        return await self.database._delete_document(self.name, query)

    async def _find_many(
        self,
        query: dict[str, Any],
        limit: int | None = None,
        sort_field: str | None = None,
        sort_direction: int = 1,
    ) -> list[dict[str, Any]]:
        return await self.database._find_documents(
            self.name,
            query,
            limit=limit,
            sort_field=sort_field,
            sort_direction=sort_direction,
        )


class Database(ConfigRepository, TicketRepository, GiveawayRepository, WelcomeRepository):
    """Banco SQLite local, assíncrono e sem serviço externo."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.connection: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()
        self._config_cache: dict[int, tuple[dict, float]] = {}
        self.config = SQLiteCollection(self, "guild_config")
        self.tickets = SQLiteCollection(self, "tickets")
        self.giveaways = SQLiteCollection(self, "giveaways")
        self.welcome_settings = SQLiteCollection(self, "welcome_settings")

    async def create_indexes(self) -> None:
        if self.connection is not None:
            return

        def initialize() -> sqlite3.Connection:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
            if sqlite3.sqlite_version_info < (3, 25, 0):
                raise RuntimeError(
                    "SQLite 3.25.0 ou superior é necessário. Atualize o Python para uma versão moderna."
                )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")
            connection.execute("PRAGMA cache_size=-4096")
            connection.execute("PRAGMA temp_store=FILE")
            connection.execute("PRAGMA mmap_size=0")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS documents (
                    collection TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    guild_id INTEGER,
                    owner_id INTEGER,
                    panel TEXT,
                    status TEXT,
                    number INTEGER,
                    ends_at TEXT,
                    ending_at TEXT,
                    message_id INTEGER,
                    data TEXT NOT NULL,
                    PRIMARY KEY (collection, doc_id)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS ticket_counters (
                    guild_id INTEGER PRIMARY KEY,
                    sequence INTEGER NOT NULL DEFAULT 0 CHECK(sequence >= 0)
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_owner ON documents(guild_id, owner_id, panel, status) WHERE collection = 'tickets'"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_recent ON documents(guild_id, number DESC) WHERE collection = 'tickets'"
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_tickets_unique_open ON documents(guild_id, owner_id, panel) WHERE collection = 'tickets' AND status = 'aberto'"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_giveaways_due ON documents(status, ends_at) WHERE collection = 'giveaways'"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_giveaways_recovery ON documents(status, ending_at) WHERE collection = 'giveaways'"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_giveaways_guild ON documents(guild_id, status, ends_at) WHERE collection = 'giveaways'"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_active_channels ON documents(status, doc_id) WHERE collection = 'tickets' AND status = 'aberto'"
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS ticket_messages (
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    author_name TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    attachments TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (channel_id, message_id)
                )"""
            )
            # A PRIMARY KEY(channel_id, message_id) already provides this lookup order.
            connection.execute("DROP INDEX IF EXISTS idx_ticket_messages_order")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS ticket_message_sync (
                    channel_id INTEGER PRIMARY KEY,
                    last_synced_message_id INTEGER NOT NULL DEFAULT 0
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS giveaway_participants (
                    giveaway_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    entries INTEGER NOT NULL DEFAULT 1 CHECK(entries >= 1),
                    joined_at TEXT NOT NULL,
                    PRIMARY KEY (giveaway_id, user_id)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS giveaway_bonus_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    giveaway_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    amount INTEGER NOT NULL CHECK(amount >= 1),
                    awarded_by INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    awarded_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_giveaway_bonus_history ON giveaway_bonus_entries(giveaway_id, user_id, id DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_giveaway_participants_order ON giveaway_participants(giveaway_id, joined_at, user_id)"
            )
            schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if schema_version < 2:
                self._migrate_giveaway_participants_sync(connection)
                connection.execute("PRAGMA user_version = 2")
            connection.commit()
            return connection

        self.connection = await asyncio.to_thread(initialize)
        logger.info("SQLite conectado em %s", self.path)

    async def close(self) -> None:
        self._config_cache.clear()
        async with self._lock:
            connection, self.connection = self.connection, None
            if connection is not None:
                task = asyncio.create_task(asyncio.to_thread(connection.close))
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    await task
                    raise
        logger.info("Conexão SQLite encerrada.")

    async def _run_locked(self, operation: Callable[[], _Result]) -> _Result:
        """Executa I/O SQLite fora do event loop e mantém o lock até a thread terminar."""
        async with self._lock:
            task = asyncio.create_task(asyncio.to_thread(operation))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                try:
                    await task
                except Exception:
                    logger.exception("Operação SQLite falhou durante o cancelamento.")
                raise

    def _require_connection(self) -> sqlite3.Connection:
        if self.connection is None:
            raise RuntimeError("Banco SQLite ainda não inicializado; chame create_indexes() primeiro.")
        return self.connection

    @staticmethod
    def _indexed_values(document: dict[str, Any]) -> tuple[Any, ...]:
        ends_at = document.get("ends_at")
        ending_at = document.get("ending_at")
        return (
            document.get("guild_id"),
            document.get("owner_id"),
            document.get("panel"),
            document.get("status"),
            document.get("number"),
            ends_at.isoformat() if isinstance(ends_at, datetime) else ends_at,
            ending_at.isoformat() if isinstance(ending_at, datetime) else ending_at,
            document.get("message_id"),
        )

    async def _insert_document(self, collection: str, document: dict[str, Any]) -> None:
        doc_id = str(document["_id"])
        data = _serialize(document)
        indexed = self._indexed_values(document)

        def insert() -> None:
            connection = self._require_connection()
            try:
                connection.execute(
                    """INSERT INTO documents (
                        collection, doc_id, guild_id, owner_id, panel, status,
                        number, ends_at, ending_at, message_id, data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (collection, doc_id, *indexed, data),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError(f"Documento duplicado em {collection}: {doc_id}") from exc

        await self._run_locked(insert)

    def _candidate_rows_sync(
        self, collection: str, query: dict[str, Any]
    ) -> sqlite3.Cursor:
        connection = self._require_connection()
        clauses = ["collection = ?"]
        params: list[Any] = [collection]
        column_map = {
            "_id": "doc_id",
            "guild_id": "guild_id",
            "owner_id": "owner_id",
            "panel": "panel",
            "status": "status",
            "number": "number",
            "message_id": "message_id",
        }
        for field, value in query.items():
            column = column_map.get(field)
            if column is None or isinstance(value, (dict, list, tuple)):
                continue
            clauses.append(f"{column} IS ?")
            params.append(str(value) if field == "_id" else int(value) if isinstance(value, bool) else value)
        sql = "SELECT doc_id, data FROM documents WHERE " + " AND ".join(clauses)
        return connection.execute(sql, params)

    async def _find_documents(
        self,
        collection: str,
        query: dict[str, Any],
        limit: int | None = None,
        sort_field: str | None = None,
        sort_direction: int = 1,
    ) -> list[dict[str, Any]]:
        def find_sync() -> list[dict[str, Any]]:
            connection = self._require_connection()
            column_map = {
                "_id": "doc_id",
                "guild_id": "guild_id",
                "owner_id": "owner_id",
                "panel": "panel",
                "status": "status",
                "number": "number",
                "ends_at": "ends_at",
                "ending_at": "ending_at",
                "message_id": "message_id",
            }
            clauses = ["collection = ?"]
            params: list[Any] = [collection]
            simple_query = True
            for field, value in query.items():
                column = column_map.get(field)
                if column is None or isinstance(value, (dict, list, tuple)):
                    simple_query = False
                    continue
                clauses.append(f"{column} IS ?")
                params.append(str(value) if field == "_id" else int(value) if isinstance(value, bool) else value)

            sort_column = column_map.get(sort_field) if sort_field else None
            sql_sort = bool(sort_column)
            sql = "SELECT data FROM documents WHERE " + " AND ".join(clauses)
            if sort_column:
                direction = "DESC" if sort_direction < 0 else "ASC"
                sql += f" ORDER BY {sort_column} {direction}"
            if limit is not None and simple_query and (sort_field is None or sql_sort):
                sql += " LIMIT ?"
                params.append(max(0, int(limit)))

            documents: list[dict[str, Any]] = []
            for row in connection.execute(sql, params):
                document = _deserialize(row["data"])
                if not _matches(document, query):
                    continue
                documents.append(document)
                if limit is not None and (sort_field is None or sql_sort) and len(documents) >= limit:
                    break

            if sort_field and not sql_sort:
                documents.sort(
                    key=lambda item: (
                        _get_path(item, sort_field)[0] is False,
                        _comparable(_get_path(item, sort_field)[1]),
                    ),
                    reverse=sort_direction < 0,
                )
            if limit is not None:
                documents = documents[: max(0, int(limit))]
            return documents

        return await self._run_locked(find_sync)

    def _migrate_giveaway_participants_sync(self, connection: sqlite3.Connection) -> None:
        """Moves legacy participant dictionaries out of giveaway JSON documents."""
        last_doc_id = ""
        while True:
            rows = connection.execute(
                """SELECT doc_id, data FROM documents
                   WHERE collection = 'giveaways' AND doc_id > ?
                   ORDER BY doc_id LIMIT 100""",
                (last_doc_id,),
            ).fetchall()
            if not rows:
                break

            for row in rows:
                last_doc_id = row["doc_id"]
                document = _deserialize(row["data"])
                participants = document.pop("participants", None)
                if not isinstance(participants, dict) or not participants:
                    if participants is not None:
                        connection.execute(
                            "UPDATE documents SET data = ? WHERE collection = 'giveaways' AND doc_id = ?",
                            (_serialize(document), row["doc_id"]),
                        )
                    continue

                winners = {str(user_id) for user_id in document.get("winners", [])}
                winner_entries = dict(document.get("winner_entries", {}))
                migrated_count = 0
                migrated_entries = 0
                for user_id, participant in participants.items():
                    if not isinstance(participant, dict):
                        continue
                    try:
                        entries = max(1, int(participant.get("entries", 1)))
                    except (TypeError, ValueError):
                        entries = 1
                    migrated_count += 1
                    migrated_entries += entries
                    joined_at = participant.get("joined_at")
                    if isinstance(joined_at, datetime):
                        joined_at = joined_at.isoformat()
                    elif not isinstance(joined_at, str):
                        joined_at = datetime.now(timezone.utc).isoformat()
                    connection.execute(
                        """INSERT OR IGNORE INTO giveaway_participants
                           (giveaway_id, user_id, entries, joined_at)
                           VALUES (?, ?, ?, ?)""",
                        (row["doc_id"], str(user_id), entries, joined_at),
                    )
                    bonus_log = participant.get("bonus_log", [])
                    for bonus in bonus_log if isinstance(bonus_log, list) else []:
                        if not isinstance(bonus, dict):
                            continue
                        awarded_at = bonus.get("awarded_at")
                        if isinstance(awarded_at, datetime):
                            awarded_at = awarded_at.isoformat()
                        elif not isinstance(awarded_at, str):
                            awarded_at = joined_at
                        try:
                            amount = max(1, int(bonus.get("amount", 1)))
                            awarded_by = int(bonus.get("awarded_by", 0))
                        except (TypeError, ValueError):
                            continue
                        connection.execute(
                            """INSERT INTO giveaway_bonus_entries
                               (giveaway_id, user_id, amount, awarded_by, reason, awarded_at)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (
                                row["doc_id"],
                                str(user_id),
                                amount,
                                awarded_by,
                                str(bonus.get("reason", ""))[:300],
                                awarded_at,
                            ),
                        )
                    if str(user_id) in winners:
                        winner_entries[str(user_id)] = entries

                document["winner_entries"] = winner_entries
                document["participant_count"] = migrated_count
                document["total_entries"] = migrated_entries
                connection.execute(
                    "UPDATE documents SET data = ? WHERE collection = 'giveaways' AND doc_id = ?",
                    (_serialize(document), row["doc_id"]),
                )

    async def get_open_ticket_channel_ids(self) -> set[int]:
        def load() -> set[int]:
            connection = self._require_connection()
            rows = connection.execute(
                "SELECT doc_id FROM documents WHERE collection = 'tickets' AND status = 'aberto'"
            )
            result: set[int] = set()
            for row in rows:
                try:
                    result.add(int(row["doc_id"]))
                except (TypeError, ValueError):
                    continue
            return result

        return await self._run_locked(load)

    async def save_ticket_messages(
        self,
        messages: list[dict[str, Any]],
        update_history_cursor: bool = False,
    ) -> None:
        if not messages:
            return

        values = [
            (
                int(item["channel_id"]),
                int(item["message_id"]),
                int(item["guild_id"]),
                int(item["author_id"]),
                str(item["author_name"]),
                str(item.get("content") or ""),
                str(item["created_at"]),
                json.dumps(item.get("attachments", []), ensure_ascii=False, separators=(",", ":")),
            )
            for item in messages
        ]

        def save() -> None:
            connection = self._require_connection()
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.executemany(
                    """INSERT INTO ticket_messages (
                       channel_id, message_id, guild_id, author_id, author_name,
                       content, created_at, attachments
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(channel_id, message_id) DO UPDATE SET
                       guild_id=excluded.guild_id,
                       author_id=excluded.author_id,
                       author_name=excluded.author_name,
                       content=excluded.content,
                       created_at=excluded.created_at,
                       attachments=excluded.attachments""",
                    values,
                )
                if update_history_cursor:
                    cursor_by_channel: dict[int, int] = {}
                    for item in messages:
                        channel_id = int(item["channel_id"])
                        cursor_by_channel[channel_id] = max(
                            cursor_by_channel.get(channel_id, 0), int(item["message_id"])
                        )
                    connection.executemany(
                        """INSERT INTO ticket_message_sync (channel_id, last_synced_message_id)
                           VALUES (?, ?) ON CONFLICT(channel_id) DO UPDATE SET
                           last_synced_message_id = MAX(last_synced_message_id, excluded.last_synced_message_id)""",
                        list(cursor_by_channel.items()),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        await self._run_locked(save)

    async def delete_ticket_messages(self, channel_id: int, message_ids: list[int]) -> None:
        if not message_ids:
            return

        def delete() -> None:
            connection = self._require_connection()
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.executemany(
                    "DELETE FROM ticket_messages WHERE channel_id = ? AND message_id = ?",
                    [(int(channel_id), int(message_id)) for message_id in message_ids],
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        await self._run_locked(delete)

    async def latest_ticket_message_id(self, channel_id: int) -> int | None:
        def latest() -> int | None:
            row = self._require_connection().execute(
                "SELECT MAX(message_id) FROM ticket_messages WHERE channel_id = ?",
                (int(channel_id),),
            ).fetchone()
            return int(row[0]) if row and row[0] is not None else None

        return await self._run_locked(latest)

    async def ticket_history_cursor(self, channel_id: int) -> int | None:
        def load() -> int | None:
            row = self._require_connection().execute(
                "SELECT last_synced_message_id FROM ticket_message_sync WHERE channel_id = ?",
                (int(channel_id),),
            ).fetchone()
            return int(row[0]) if row and row[0] is not None else None

        return await self._run_locked(load)

    async def get_ticket_message_page(
        self, channel_id: int, after_message_id: int = 0, limit: int = 250
    ) -> list[dict[str, Any]]:
        safe_limit = min(1000, max(1, int(limit)))

        def load() -> list[dict[str, Any]]:
            rows = self._require_connection().execute(
                """SELECT message_id, author_id, author_name, content, created_at, attachments
                   FROM ticket_messages
                   WHERE channel_id = ? AND message_id > ?
                   ORDER BY message_id ASC LIMIT ?""",
                (int(channel_id), int(after_message_id), safe_limit),
            )
            return [
                {
                    "message_id": int(row["message_id"]),
                    "author_id": int(row["author_id"]),
                    "author_name": row["author_name"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "attachments": json.loads(row["attachments"]),
                }
                for row in rows
            ]

        return await self._run_locked(load)

    async def get_giveaway_participant(self, giveaway_id: str, user_id: int) -> dict[str, Any] | None:
        def load() -> dict[str, Any] | None:
            row = self._require_connection().execute(
                "SELECT entries, joined_at FROM giveaway_participants WHERE giveaway_id = ? AND user_id = ?",
                (str(giveaway_id), str(user_id)),
            ).fetchone()
            if row is None:
                return None
            return {"entries": int(row["entries"]), "joined_at": row["joined_at"]}

        return await self._run_locked(load)

    async def get_giveaway_bonus_log(
        self, giveaway_id: str, user_id: int, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        safe_limit = min(100, max(1, int(limit)))
        safe_offset = max(0, int(offset))

        def load() -> list[dict[str, Any]]:
            rows = self._require_connection().execute(
                """SELECT amount, awarded_by, reason, awarded_at FROM giveaway_bonus_entries
                   WHERE giveaway_id = ? AND user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?""",
                (str(giveaway_id), str(user_id), safe_limit, safe_offset),
            )
            return [
                {
                    "amount": int(row["amount"]),
                    "awarded_by": int(row["awarded_by"]),
                    "reason": row["reason"],
                    "awarded_at": row["awarded_at"],
                }
                for row in rows
            ]

        return await self._run_locked(load)

    async def get_giveaway_participants_page(
        self, giveaway_id: str, limit: int = 25, offset: int = 0
    ) -> list[dict[str, Any]]:
        safe_limit = min(100, max(1, int(limit)))
        safe_offset = max(0, int(offset))

        def load() -> list[dict[str, Any]]:
            rows = self._require_connection().execute(
                """SELECT user_id, entries, joined_at FROM giveaway_participants
                   WHERE giveaway_id = ? ORDER BY joined_at ASC, user_id ASC
                   LIMIT ? OFFSET ?""",
                (str(giveaway_id), safe_limit, safe_offset),
            )
            return [
                {"user_id": row["user_id"], "entries": int(row["entries"]), "joined_at": row["joined_at"]}
                for row in rows
            ]

        return await self._run_locked(load)

    async def select_giveaway_winners(
        self, giveaway_id: str, count: int, excluded: set[str] | None = None
    ) -> list[dict[str, Any]]:
        safe_count = min(100, max(0, int(count)))
        excluded_ids = {str(item) for item in (excluded or set())}
        if safe_count == 0:
            return []

        def select() -> list[dict[str, Any]]:
            connection = self._require_connection()
            selected: list[dict[str, Any]] = []
            unavailable = set(excluded_ids)
            for _ in range(safe_count):
                where = "giveaway_id = ?"
                params: list[Any] = [str(giveaway_id)]
                if unavailable:
                    placeholders = ",".join("?" for _ in unavailable)
                    where += f" AND user_id NOT IN ({placeholders})"
                    params.extend(sorted(unavailable))
                total_row = connection.execute(
                    f"SELECT COALESCE(SUM(entries), 0) FROM giveaway_participants WHERE {where}",
                    params,
                ).fetchone()
                total = int(total_row[0] or 0)
                if total <= 0:
                    break
                target = secrets.randbelow(total) + 1
                winner_row = connection.execute(
                    f"""SELECT user_id, entries FROM (
                           SELECT user_id, entries,
                                  SUM(entries) OVER (ORDER BY user_id ROWS UNBOUNDED PRECEDING) AS cumulative
                           FROM giveaway_participants WHERE {where}
                       ) WHERE cumulative >= ? ORDER BY user_id LIMIT 1""",
                    [*params, target],
                ).fetchone()
                if winner_row is None:
                    break
                user_id = str(winner_row["user_id"])
                unavailable.add(user_id)
                selected.append({"user_id": user_id, "entries": int(winner_row["entries"])})
            return selected

        return await self._run_locked(select)

    async def _update_document(
        self, collection: str, query: dict[str, Any], update: dict[str, Any], upsert: bool
    ) -> UpdateResult:
        def update_sync() -> UpdateResult:
            connection = self._require_connection()
            connection.execute("BEGIN IMMEDIATE")
            try:
                rows = self._candidate_rows_sync(collection, query)
                matched = None
                try:
                    for row in rows:
                        candidate = _deserialize(row["data"])
                        if _matches(candidate, query):
                            matched = candidate
                            break
                finally:
                    rows.close()

                if matched is None:
                    if not upsert:
                        connection.commit()
                        return UpdateResult()
                    matched = {
                        key: value
                        for key, value in query.items()
                        if not key.startswith("$") and not isinstance(value, dict)
                    }
                    if "_id" not in matched:
                        raise ValueError("Upsert precisa conter _id no filtro.")
                    _apply_update(matched, update)
                    indexed = self._indexed_values(matched)
                    connection.execute(
                        """INSERT INTO documents (
                            collection, doc_id, guild_id, owner_id, panel, status,
                            number, ends_at, ending_at, message_id, data
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (collection, str(matched["_id"]), *indexed, _serialize(matched)),
                    )
                    connection.commit()
                    return UpdateResult(matched_count=0, modified_count=0)

                old_data = _serialize(matched)
                _apply_update(matched, update)
                new_data = _serialize(matched)
                if old_data != new_data:
                    indexed = self._indexed_values(matched)
                    connection.execute(
                        """UPDATE documents SET guild_id=?, owner_id=?, panel=?, status=?,
                            number=?, ends_at=?, ending_at=?, message_id=?, data=?
                            WHERE collection=? AND doc_id=?""",
                        (*indexed, new_data, collection, str(matched["_id"])),
                    )
                connection.commit()
                return UpdateResult(matched_count=1, modified_count=int(old_data != new_data))
            except Exception:
                connection.rollback()
                raise

        return await self._run_locked(update_sync)

    async def _delete_document(self, collection: str, query: dict[str, Any]) -> DeleteResult:
        def delete_sync() -> DeleteResult:
            connection = self._require_connection()
            connection.execute("BEGIN IMMEDIATE")
            try:
                rows = self._candidate_rows_sync(collection, query)
                matched = None
                try:
                    for row in rows:
                        if _matches(_deserialize(row["data"]), query):
                            matched = row["doc_id"]
                            break
                finally:
                    rows.close()
                if matched is None:
                    connection.commit()
                    return DeleteResult()
                cursor = connection.execute(
                    "DELETE FROM documents WHERE collection=? AND doc_id=?", (collection, matched)
                )
                connection.commit()
                return DeleteResult(deleted_count=cursor.rowcount)
            except Exception:
                connection.rollback()
                raise

        return await self._run_locked(delete_sync)

    async def _next_ticket_sequence(self, guild_id: int) -> int:
        def next_sequence() -> int:
            connection = self._require_connection()
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO ticket_counters (guild_id, sequence) VALUES (?, 1)
                       ON CONFLICT(guild_id) DO UPDATE SET sequence = sequence + 1""",
                    (guild_id,),
                )
                row = connection.execute(
                    "SELECT sequence FROM ticket_counters WHERE guild_id = ?", (guild_id,)
                ).fetchone()
                connection.commit()
                return int(row[0])
            except Exception:
                connection.rollback()
                raise

        return await self._run_locked(next_sequence)


__all__ = [
    "Database",
    "default_config",
    "default_ticket_panels",
]
