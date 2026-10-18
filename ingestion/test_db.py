"""Tests for db.py against the real MongoDB.

Runs offline checks on the placeholder contract first, then live roundtrip
tests against the DB. Skips itself when MONGO_DB_CONNECTION_STRING isn't
configured or the server can't be reached. Never leaves test data behind.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

import os
from datetime import UTC, datetime

import db

# --- offline contract checks (no DB needed) ---
assert isinstance(db._PLACEHOLDER_REPOS, list) and all("/" in r for r in db._PLACEHOLDER_REPOS)
assert db._PLACEHOLDER_MEMBERS and all(
    set(m) == {"github_username", "linear_email", "member_name"} for m in db._PLACEHOLDER_MEMBERS
)

if not os.getenv("MONGO_DB_CONNECTION_STRING"):
    print("all asserts passed (DB tests skipped: MONGO_DB_CONNECTION_STRING not set)")
    raise SystemExit(0)

try:
    db._get_db()
except db.DBError as exc:
    print(f"all asserts passed (DB tests skipped: {exc})")
    raise SystemExit(0)

# --- live: read paths must return well-formed data ---
repos = db.get_repos()
assert isinstance(repos, list) and repos, repos
assert all(isinstance(r, str) and r.count("/") == 1 for r in repos), repos

members = db.get_team_members()
assert isinstance(members, list) and members, members
assert all(
    m.get("github_username") and m.get("linear_email") and m.get("member_name")
    for m in members
), members

# --- live: write path roundtrip with a clearly-marked test member ---
TEST_MEMBER = {
    "github_username": "test-user__roll-call__",
    "linear_email": "test-user__roll-call__@invalid",
    "member_name": "DB TEST — safe to delete",
}
PAYLOAD = {"member_name": TEST_MEMBER["member_name"], "pull_requests": [], "issues": [], "probe": True}
SUMMARY = "test summary — safe to delete"

db.store_member_data(TEST_MEMBER, PAYLOAD, SUMMARY)

stored = db._get_db()["daily_reports"].find_one(
    {"github_username": TEST_MEMBER["github_username"]}, {"_id": 0}
)
assert stored, "roundtrip doc not found after store"
assert stored["summary"] == SUMMARY
assert stored["input_data"] == PAYLOAD
assert stored["member_name"] == TEST_MEMBER["member_name"]
assert stored["date"] == datetime.now(UTC).date().isoformat()

# re-store must update, not duplicate
db.store_member_data(TEST_MEMBER, PAYLOAD, SUMMARY + " v2")
count = db._get_db()["daily_reports"].count_documents({"github_username": TEST_MEMBER["github_username"]})
assert count == 1, f"upsert duplicated: {count} docs"
stored = db._get_db()["daily_reports"].find_one({"github_username": TEST_MEMBER["github_username"]})
assert stored["summary"] == SUMMARY + " v2"

# cleanup: remove every trace of the test member
deleted = db._get_db()["daily_reports"].delete_many({"github_username": TEST_MEMBER["github_username"]})
print(f"cleaned up {deleted.deleted_count} test document(s)")
assert deleted.deleted_count == 1

print("all asserts passed (DB live tests included)")
