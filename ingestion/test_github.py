"""Offline asserts for the filtering/matching logic in github.py (no network)."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from github import _commit_identifiers, todays_commits, user_participates

TODAY = date(2026, 3, 10)

commits = [
    {"sha": "a", "commit": {"author": {"date": "2026-03-10T12:00:00Z", "email": "dev@x.com", "name": "Dev"}, "message": "fix bug"}, "author": {"login": "devuser"}},
    {"sha": "b", "commit": {"author": {"date": "2026-03-09T12:00:00Z", "email": "dev@x.com", "name": "Dev"}, "message": "old work"}, "author": {"login": "devuser"}},
    {"sha": "c", "commit": {"author": {"date": "2026-03-10T08:00:00Z", "email": "other@x.com", "name": "Other"}, "message": "other"}, "author": {"login": "otheruser"}},
]

kept = todays_commits(commits, TODAY)
assert [c["sha"] for c in kept] == ["a", "c"], kept

assert _commit_identifiers(commits) == {"devuser", "dev@x.com", "otheruser", "other@x.com"}

pr = {"user": {"login": "someoneelse"}, "requested_reviewers": [], "assignees": []}
assert not user_participates("devuser", pr, todays_commits(commits, date(2026, 3, 11)))  # no commits that day
assert user_participates("devuser", pr, todays_commits(commits, TODAY))                   # via today's commit
assert user_participates("dev@x.com", pr, commits)         # via email
assert user_participates("reviewer", {"user": {"login": "x"}, "requested_reviewers": [{"login": "Reviewer"}], "assignees": []}, [])
assert user_participates("DevUser", {"user": {"login": "devuser"}, "requested_reviewers": [], "assignees": []}, [])  # case-insensitive

# comment-preserving read of repos.txt / users.txt
print("all asserts passed")
