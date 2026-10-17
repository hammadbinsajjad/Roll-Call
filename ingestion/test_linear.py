"""Offline asserts for the filtering/matching logic in linear.py (no network)."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from linear import issue_record, todays_comments, user_participates

TODAY = date(2026, 10, 17)

comments = [
    {"body": "done", "createdAt": "2026-10-17T12:00:00Z", "user": {"email": "dev@x.com", "name": "Dev"}},
    {"body": "old", "createdAt": "2026-10-16T12:00:00Z", "user": {"email": "dev@x.com", "name": "Dev"}},
    {"body": "other", "createdAt": "2026-10-17T08:00:00Z", "user": {"email": "other@x.com", "name": "Other"}},
]

kept = todays_comments(comments, TODAY)
assert [c["body"] for c in kept] == ["done", "other"], kept

issue = {
    "identifier": "ROLL-1",
    "title": "t",
    "description": "d",
    "state": {"name": "In Progress"},
    "assignee": {"email": "dev@x.com", "name": "Dev", "displayName": "devuser"},
    "creator": {"email": "boss@x.com", "name": "Boss"},
    "createdAt": "2026-10-17T10:00:00Z",
    "updatedAt": "2026-10-17T12:00:00Z",
    "team": {"name": "Team X"},
    "labels": {"nodes": [{"name": "bug"}]},
    "comments": {
        "nodes": [
            {"body": "other's comment", "createdAt": "2026-10-17T08:00:00Z", "user": {"email": "other@x.com", "name": "Other"}},
            {"body": "old comment", "createdAt": "2026-10-16T09:00:00Z", "user": {"email": "dev@x.com", "name": "Dev"}},
        ]
    },
}

rec = issue_record(issue, TODAY)
assert rec["identifier"] == "ROLL-1" and rec["state"] == "In Progress"
assert rec["labels"] == ["bug"]
assert [c["body"] for c in rec["comments"]] == ["other's comment"]  # only today's comments kept

assert user_participates("dev@x.com", rec)      # assignee email
assert user_participates("devuser", rec)        # assignee name
assert user_participates("boss@x.com", rec)     # creator
assert user_participates("other@x.com", rec)    # today's comment author
assert not user_participates("quiet@x.com", rec)
assert not user_participates("devuser", issue_record(
    {**issue, "assignee": {"email": "boss@x.com", "name": "Boss"}, "creator": {"email": "boss@x.com"}}, TODAY))  # no tie besides an old comment

print("all asserts passed")
