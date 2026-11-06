from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any



class GiveawayRepository:
    async def create_giveaway(self, giveaway: dict) -> None:
        document = dict(giveaway)
        document.pop("participants", None)
        await self.giveaways.insert_one(document)

    async def get_giveaway(self, giveaway_id: str) -> dict | None:
        return await self.giveaways.find_one({"_id": giveaway_id})

    async def update_giveaway(self, giveaway_id: str, data: dict) -> bool:
        if "participants" in data:
            raise ValueError("Participantes devem ser alterados pelos métodos do repositório.")
        result = await self.giveaways.update_one({"_id": giveaway_id}, {"$set": data})
        return result.matched_count > 0

    async def delete_giveaway(self, giveaway_id: str) -> None:
        await self.giveaways.delete_one({"_id": giveaway_id, "status": "creating"})

    async def join_giveaway(
        self, giveaway_id: str, user_id: int, entries: int, joined_at: datetime
    ) -> bool:
        user_key = str(user_id)
        entry_count = max(1, int(entries))
        timestamp = joined_at.isoformat()

        from src.utils.database import _deserialize, _serialize

        def join() -> bool:
            connection = self._require_connection()
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT data FROM documents WHERE collection = 'giveaways' AND doc_id = ?",
                    (str(giveaway_id),),
                ).fetchone()
                if row is None:
                    connection.commit()
                    return False
                document = _deserialize(row["data"])
                if document.get("status") != "active":
                    connection.commit()
                    return False

                cursor = connection.execute(
                    """INSERT OR IGNORE INTO giveaway_participants
                       (giveaway_id, user_id, entries, joined_at)
                       VALUES (?, ?, ?, ?)""",
                    (str(giveaway_id), user_key, entry_count, timestamp),
                )
                if cursor.rowcount != 1:
                    connection.commit()
                    return False

                document["participant_count"] = int(document.get("participant_count", 0)) + 1
                document["total_entries"] = int(document.get("total_entries", 0)) + entry_count
                connection.execute(
                    "UPDATE documents SET data = ? WHERE collection = 'giveaways' AND doc_id = ?",
                    (_serialize(document), str(giveaway_id)),
                )
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise

        return await self._run_locked(join)

    async def add_giveaway_entries(
        self,
        giveaway_id: str,
        user_id: int,
        amount: int,
        awarded_by: int,
        reason: str,
        awarded_at: datetime | None = None,
    ) -> bool:
        bonus_amount = max(1, int(amount))
        user_key = str(user_id)
        bonus_record = {
            "amount": bonus_amount,
            "awarded_by": int(awarded_by),
            "reason": str(reason)[:300],
            "awarded_at": (awarded_at or datetime.now(timezone.utc)).isoformat(),
        }

        from src.utils.database import _deserialize, _serialize

        def add_entries() -> bool:
            connection = self._require_connection()
            connection.execute("BEGIN IMMEDIATE")
            try:
                giveaway_row = connection.execute(
                    "SELECT data FROM documents WHERE collection = 'giveaways' AND doc_id = ?",
                    (str(giveaway_id),),
                ).fetchone()
                if giveaway_row is None:
                    connection.commit()
                    return False
                document = _deserialize(giveaway_row["data"])
                if document.get("status") != "active":
                    connection.commit()
                    return False

                participant_row = connection.execute(
                    "SELECT 1 FROM giveaway_participants WHERE giveaway_id = ? AND user_id = ?",
                    (str(giveaway_id), user_key),
                ).fetchone()
                if participant_row is None:
                    connection.commit()
                    return False

                connection.execute(
                    """INSERT INTO giveaway_bonus_entries
                       (giveaway_id, user_id, amount, awarded_by, reason, awarded_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        str(giveaway_id),
                        user_key,
                        bonus_amount,
                        bonus_record["awarded_by"],
                        bonus_record["reason"],
                        bonus_record["awarded_at"],
                    ),
                )
                connection.execute(
                    """UPDATE giveaway_participants SET entries = entries + ?
                       WHERE giveaway_id = ? AND user_id = ?""",
                    (bonus_amount, str(giveaway_id), user_key),
                )
                document["total_entries"] = int(document.get("total_entries", 0)) + bonus_amount
                connection.execute(
                    "UPDATE documents SET data = ? WHERE collection = 'giveaways' AND doc_id = ?",
                    (_serialize(document), str(giveaway_id)),
                )
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise

        return await self._run_locked(add_entries)

    async def claim_giveaway_end(
        self, giveaway_id: str, force: bool = False, now: datetime | None = None
    ) -> bool:
        current = now or datetime.now(timezone.utc)
        query = {"_id": giveaway_id, "status": "active"}
        if not force:
            query["ends_at"] = {"$lte": current}
        result = await self.giveaways.update_one(
            query, {"$set": {"status": "ending", "ending_at": current}}
        )
        return result.modified_count > 0

    async def recover_giveaway_end(
        self,
        giveaway_id: str,
        stale_before: datetime,
        now: datetime | None = None,
    ) -> bool:
        result = await self.giveaways.update_one(
            {"_id": giveaway_id, "status": "ending", "ending_at": {"$lte": stale_before}},
            {"$set": {"ending_at": now or datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0

    async def due_giveaways(
        self, now: datetime | None = None, limit: int = 100
    ) -> list[dict]:
        current = now or datetime.now(timezone.utc)
        stale_before = current - timedelta(minutes=2)
        safe_limit = min(250, max(1, int(limit)))
        from src.utils.database import _deserialize

        def load_due() -> list[dict]:
            connection = self._require_connection()
            rows = connection.execute(
                """SELECT data FROM documents
                   WHERE collection = 'giveaways' AND (
                       (status = 'active' AND ends_at IS NOT NULL AND ends_at <= ?)
                       OR
                       (status = 'ending' AND ending_at IS NOT NULL AND ending_at <= ?)
                   )
                   ORDER BY COALESCE(ends_at, ending_at) ASC
                   LIMIT ?""",
                (current.isoformat(), stale_before.isoformat(), safe_limit),
            )
            return [_deserialize(row["data"]) for row in rows]

        return await self._run_locked(load_due)
