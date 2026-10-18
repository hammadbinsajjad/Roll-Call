"""DB layer for Roll-Call ingestion (MongoDB).

Collections:
  - repos         {name: "owner/repo"}                          <- get_repos()
  - team_members  {github_username, linear_email, member_name}  <- get_team_members()
  - daily_reports {date, github_username, linear_email,
                   member_name, input_data, summary, stored_at} <- store_member_data()

get_repos()/get_team_members() fall back to the built-in placeholder
values below when their collections are empty, so the pipeline keeps
running before any seed data is inserted.
"""

import os
from datetime import UTC, datetime

from pymongo import MongoClient


class DBError(RuntimeError):
    pass


# values that used to live in repos.txt / users.txt; fallback when the
# collections are empty (until the DB is fully seeded)
_PLACEHOLDER_REPOS = ["hammadbinsajjad/Roll-Call"]
_PLACEHOLDER_MEMBERS = [{
    "github_username": "hammadbinsajjad",
    "linear_email": "supperhammad2002@gmail.com",
    "member_name": "Hammad Bin Sajjad",
}]

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        uri = os.getenv("MONGO_DB_CONNECTION_STRING")
        if not uri:
            raise DBError("MONGO_DB_CONNECTION_STRING is not set (ingestion/.env or environment).")
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        try:
            _client.admin.command("ping")  # fail fast with a clear error
        except Exception as exc:
            raise DBError(f"Cannot reach MongoDB: {exc}") from exc
        _db = _client["roll_call"]
    return _db


def get_repos():
    """Return the repos to monitor as ["owner/repo", ...]."""
    docs = list(_get_db()["repos"].find({}, {"_id": 0}))
    repos = [doc["name"] for doc in docs if doc.get("name")]
    if repos:
        return repos
    print("db: repos collection empty — using placeholder repos")
    return list(_PLACEHOLDER_REPOS)


def get_team_members():
    """Return the team as a list of dicts, one per member:

        [{"github_username": ..., "linear_email": ..., "member_name": ...}]
    """
    docs = list(_get_db()["team_members"].find({}, {"_id": 0}))
    members = [
        {
            "github_username": doc.get("github_username"),
            "linear_email": doc.get("linear_email"),
            "member_name": doc.get("member_name"),
        }
        for doc in docs
        if doc.get("github_username") and doc.get("linear_email")
    ]
    if members:
        return members
    print("db: team_members collection empty — using placeholder members")
    return [dict(m) for m in _PLACEHOLDER_MEMBERS]


def store_member_data(member, input_data, summary):
    """Store one member's day: their LLM input data and the generated summary.

    Upserts into daily_reports, keyed by (UTC date, member), so re-running
    the ingestion on the same day replaces that member's entry instead of
    duplicating it.
    """
    today = datetime.now(UTC).date().isoformat()
    doc = {
        "date": today,
        "github_username": member.get("github_username"),
        "linear_email": member.get("linear_email"),
        "member_name": member.get("member_name"),
        "input_data": input_data,
        "summary": summary,
        "stored_at": datetime.now(UTC).isoformat(),
    }
    try:
        _get_db()["daily_reports"].update_one(
            {"date": today, "github_username": doc["github_username"]},
            {"$set": doc},
            upsert=True,
        )
    except Exception as exc:
        raise DBError(f"Failed to store member data: {exc}") from exc
