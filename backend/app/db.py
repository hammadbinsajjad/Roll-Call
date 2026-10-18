"""Mongo layer for the backend (roll_call DB, shared with ingestion).

Collections the backend owns: users, chats.
Read-only: daily_reports. Read + write via /config: repos, team_members.
"""

from datetime import UTC, datetime

from pymongo import ASCENDING, MongoClient

_client = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        from . import config
        if not config.MONGO_DB_CONNECTION_STRING:
            raise RuntimeError("MONGO_DB_CONNECTION_STRING is not set (backend/.env or environment).")
        _client = MongoClient(
            config.MONGO_DB_CONNECTION_STRING,
            serverSelectionTimeoutMS=5000,
        )
        try:
            _client.admin.command("ping")  # fail fast with a clear error
        except Exception as exc:
            raise RuntimeError(f"Cannot reach MongoDB: {exc}") from exc
        _db = _client["roll_call"]
        _ensure_indexes(_db)
    return _db


def _ensure_indexes(db):
    db["users"].create_index([("username", ASCENDING)], unique=True)
    db["chats"].create_index([("chat_id", ASCENDING)], unique=True)
    db["chats"].create_index([("username", ASCENDING), ("updated_at", ASCENDING)])
    # shared with ingestion (it upserts daily_reports on this key)
    db["daily_reports"].create_index([("date", ASCENDING), ("github_username", ASCENDING)])


def today_iso() -> str:
    return datetime.now(UTC).date().isoformat()


def bump_usage(username: str, n: int):
    """Add n to the user's per-UTC-day message counter, rolling the date
    forward in place when it's behind today."""
    today = today_iso()
    doc = get_db()["users"].find_one({"username": username}, {"usage_date": 1})
    if doc and doc.get("usage_date") == today:
        get_db()["users"].update_one({"username": username}, {"$inc": {"usage_count": n}})
    else:
        get_db()["users"].update_one(
            {"username": username},
            {"$set": {"usage_date": today, "usage_count": n}},
        )


def daily_usage(username: str) -> int:
    doc = get_db()["users"].find_one({"username": username}, {"usage_date": 1, "usage_count": 1})
    if not doc or doc.get("usage_date") != today_iso():
        return 0
    return doc.get("usage_count", 0)


__all__ = ["get_db", "bump_usage", "daily_usage", "today_iso"]
